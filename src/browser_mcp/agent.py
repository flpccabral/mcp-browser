"""Browser Agent orchestrating LLM-driven browser automation."""

import json
import logging
import os
import re
import time
from typing import Any, cast

from .browser_manager import BrowserManager
from .llm_client import LLMClient

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = """You are an expert web automation agent. You control a browser and can interact with web pages to complete tasks.

## THINKING
Analyze the current page state and the task progress. Be concise but thorough. Consider what has been done, what remains, and what the next logical step is.

## ACTION
Use exactly one tool per turn. Respond with a JSON object inside a markdown code block (```json ... ```) containing:
- "thought": your reasoning (concise, in English or Portuguese)
- "tool": the exact tool name to use (must be one of the listed tools)
- "params": a dict of parameters for that tool
- "is_complete": boolean — true only when the task is fully done and no more actions are needed
- "report": optional markdown summary when is_complete is true (what was accomplished, key findings, data extracted)
- "scratchpad_note": optional string to append to your working memory for future iterations

## RULES
1. PREFER @e refs over CSS selectors when they are available in the observation. @e refs are stable accessibility tree identifiers (e.g., @e3, @e12).
2. If no @e ref is available, use CSS selectors (IDs, classes, attributes) or visible text.
3. Only interact with elements that exist in the current page observation.
4. Do not hallucinate elements or attributes.
5. If stuck, use browser_screenshot to see the current state.
6. Keep actions atomic and minimal — one interaction per turn.
7. If a form submission fails, verify the selector and try again.
8. For data extraction, use browser_get_content with a selector or browser_execute_javascript.
9. NEVER use browser_execute_javascript to click links or navigate. JS click events (element.click()) have isTrusted=false and are blocked by Google News and many SPAs. Always use browser_click for any click/navigation action — it dispatches real trusted events via CDP.
10. If you need to wait for a page to load or an element to appear, use browser_wait with condition="network_idle" or condition="element_visible".
11. Do not use browser_scroll unless absolutely necessary; prefer navigating directly or using element selectors.
12. Always set is_complete=true when the task is done, with a clear report.

## CURRENT STATE
Available tools:
{tools_description}

Current page: {current_url}
Page title: {page_title}

Scratchpad (your working memory):
{scratchpad}

Iteration: {iteration}/{max_iterations}
Pending network requests: {network_count}
"""


TOOLS_DESCRIPTION = """- browser_navigate: { "url": "string" } — Navigate to a URL.
- browser_click: { "selector": "string", "by": "css" | "xpath" | "text" | "coordinates" | "ref" } — Click an element by CSS selector (default), xpath, visible text, coordinates "x,y", or @e ref (e.g., @e3).
- browser_type: { "selector": "string", "text": "string", "clear": bool, "by": "css" | "ref" } — Type text into an input/textarea. Use @e ref for selector when available. Set clear=false to append instead of replacing.
- browser_select_option: { "selector": "string", "value": "string" } — Select an option in a <select> element by value.
- browser_screenshot: { "filename": "string" (optional), "full_page": bool (optional) } — Capture a screenshot. If no filename is provided, one is auto-generated.
- browser_get_content: { "selector": "string" (optional), "as_html": bool (optional) } — Get text content (or HTML) of the page or a specific element.
- browser_execute_javascript: { "code": "string" } — Execute JavaScript on the page for DATA EXTRACTION only. ⚠️ NEVER use for clicking/navigation — events have isTrusted=false. Use browser_click instead.
- browser_get_attributes: { "selector": "string", "attribute": "string" (optional) } — Get all attributes of an element, or a specific attribute if provided.
- browser_get_network_log: { "filter_url": "string" (optional), "filter_method": "string" (optional) } — Get network request logs as JSON.
- browser_export_har: { "path": "string" } — Export network log to a HAR file.
- browser_manage_session: { "action": "string", ... } — Manage session actions: get_cookies, set_cookies, clear_cookies, new_tab, list_tabs, close_tab, resize_viewport.
- browser_wait: { "condition": "element_visible" | "element_hidden" | "network_idle" | "timeout", "selector": "string" (optional), "timeout": number (optional, ms) } — Wait for a condition.
- browser_go_back: {} — Go back in browser history.
- browser_go_forward: {} — Go forward in browser history.
- browser_reload: {} — Reload the current page.
- browser_hover: { "selector": "string", "by": "css" | "ref" } — Hover over an element. Use @e ref when available.
- browser_press_key: { "key": "string", "selector": "string" (optional) } — Press a key (e.g., "Enter", "Tab") on a specific element or globally.
- browser_upload_file: { "selector": "string", "file_path": "string" } — Upload a file to a file input.
- browser_accessibility_tree: {} — Get the accessibility tree snapshot of the current page (returns JSON).
"""


class BrowserAgent:
    """Agent that drives browser automation via an LLM."""

    def __init__(
        self,
        browser_manager: BrowserManager,
        llm_client: LLMClient,
        max_iterations: int = 30,
        max_consecutive_errors: int = 3,
        screenshot_on_action: bool = False,
        output_dir: str = "/tmp/browser_agent",
    ):
        self.browser_manager = browser_manager
        self.llm_client = llm_client
        self.max_iterations = max_iterations
        self.max_consecutive_errors = max_consecutive_errors
        self.screenshot_on_action = screenshot_on_action
        self.output_dir = output_dir

        os.makedirs(self.output_dir, exist_ok=True)

        self.scratchpad: str = ""
        self.action_history: list[dict[str, Any]] = []
        self.screenshots: list[str] = []
        self.errors: list[str] = []
        self.consecutive_errors: int = 0

    async def execute_task(self, task_prompt: str) -> dict[str, Any]:
        """Main execution loop: OBSERVE -> THINK -> CHECK -> ACT -> RECORD."""
        self.scratchpad = ""
        self.action_history = []
        self.screenshots = []
        self.errors = []
        self.consecutive_errors = 0

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": "placeholder"},
            {"role": "user", "content": f"Task: {task_prompt}\n\nBegin."},
        ]

        for iteration in range(1, self.max_iterations + 1):
            # OBSERVE
            observation = await self._observe()

            # Update system prompt with current state
            system_content = AGENT_SYSTEM_PROMPT.format(
                tools_description=TOOLS_DESCRIPTION,
                current_url=observation.get("url", "unknown"),
                page_title=observation.get("title", "unknown"),
                scratchpad=self.scratchpad or "(empty)",
                iteration=iteration,
                max_iterations=self.max_iterations,
                network_count=observation.get("network_count", 0),
            )

            # Ensure system message is first
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] = system_content
            else:
                messages.insert(0, {"role": "system", "content": system_content})

            # Append observation as user message
            observation_text = self._format_observation(observation)
            messages.append({"role": "user", "content": observation_text})

            # Prune to avoid token overflow
            messages = self._prune_messages(messages)

            # THINK (LLM call)
            try:
                response_text = await self.llm_client.chat(messages)
                self.consecutive_errors = 0
            except Exception as exc:
                error_msg = f"LLM call failed at iteration {iteration}: {exc}"
                self.errors.append(error_msg)
                self.consecutive_errors += 1
                if self.consecutive_errors >= self.max_consecutive_errors:
                    return self._build_final_result(
                        success=False,
                        report=f"Task failed after {self.max_consecutive_errors} consecutive errors. Latest: {error_msg}",
                    )
                # Retry with error feedback
                messages.append({"role": "user", "content": f"Error: {error_msg}. Please retry."})
                continue

            # Parse LLM response
            parsed = self._parse_response(response_text)
            if parsed is None:
                error_msg = f"Could not parse LLM response at iteration {iteration}: {response_text[:200]}"
                self.errors.append(error_msg)
                self.consecutive_errors += 1
                if self.consecutive_errors >= self.max_consecutive_errors:
                    return self._build_final_result(
                        success=False,
                        report=f"Task failed after {self.max_consecutive_errors} consecutive parse errors. Latest: {error_msg}",
                    )
                messages.append({"role": "user", "content": f"Error: {error_msg}. Please respond with a JSON code block."})
                continue

            # Append assistant response to history
            messages.append({"role": "assistant", "content": response_text})

            # CHECK is_complete
            if parsed.get("is_complete"):
                report = parsed.get("report", "Task completed without additional details.")
                return self._build_final_result(success=True, report=report)

            # ACT: execute tool
            tool_name = parsed.get("tool", "")
            params = parsed.get("params", {})
            thought = parsed.get("thought", "")
            scratchpad_note = parsed.get("scratchpad_note", "")

            # Update scratchpad
            if scratchpad_note:
                self.scratchpad += f"\n{scratchpad_note}"
            self.scratchpad += f"\n[Iter {iteration}] Thought: {thought}\nAction: {tool_name}({json.dumps(params, ensure_ascii=False)})"

            result = await self._execute_tool(tool_name, params)

            # RECORD
            self.action_history.append({
                "iteration": iteration,
                "tool": tool_name,
                "params": params,
                "thought": thought,
                "result": result,
            })

            if self.screenshot_on_action and tool_name != "browser_screenshot":
                screenshot_path = await self._take_screenshot(f"iter_{iteration}_{tool_name}.png")
                self.screenshots.append(screenshot_path)

            # Feed result back to LLM
            messages.append({"role": "user", "content": f"Action result:\n{result}"})

        # Max iterations reached without completion
        return self._build_final_result(
            success=False,
            report=f"Task reached max iterations ({self.max_iterations}) without completing.",
        )

    async def _observe(self) -> dict[str, Any]:
        """Capture current page state using Playwright accessibility tree."""
        try:
            url = await self.browser_manager.get_url()
        except Exception:
            url = "unknown"
        try:
            title = await self.browser_manager.get_title()
        except Exception:
            title = "unknown"
        try:
            visible_text = await self.browser_manager.get_visible_text()
        except Exception:
            visible_text = "(could not retrieve text)"

        # Try accessibility tree first; fallback to old JS method if unavailable
        try:
            tree = await self.browser_manager.get_accessibility_tree()
            root = tree.get("tree", tree)
            if not root:
                root = tree
            flat_nodes: list[dict[str, Any]] = []
            self._flatten_accessibility_nodes(root, flat_nodes)

            interactive_roles = {
                "button", "link", "textbox", "checkbox", "radio", "combobox",
                "listbox", "menuitem", "menuitemcheckbox", "menuitemradio",
                "option", "searchbox", "switch", "tab", "treeitem", "spinbutton",
                "slider", "progressbar", "scrollbar", "heading", "navigation",
                "search", "tabpanel", "tree", "grid", "cell", "rowheader", "columnheader",
            }
            interactive_elements = []
            for node in flat_nodes:
                role = (node.get("role") or "").lower()
                name = node.get("name") or ""
                if role in interactive_roles or (role and name):
                    interactive_elements.append({
                        "ref": node.get("ref", ""),
                        "role": role,
                        "name": name[:80],
                    })

            total_elements = len(interactive_elements)
            if total_elements > 30:
                shown_elements = interactive_elements[:30]
            else:
                shown_elements = interactive_elements
            elements_summary = "\n".join(
                f"- {el['ref']} | role={el['role']} | name={el['name']}"
                for el in shown_elements
            )
            if total_elements > 30:
                elements_summary += f"\n\n... ({total_elements - 30} more elements)"
        except Exception as exc:
            logger.warning(
                "Accessibility tree processing failed: %s. Falling back to legacy JS method.",
                exc,
                exc_info=True,
            )
            # Fallback to legacy JS method
            try:
                interactive_elements = await self.browser_manager.get_interactive_elements()
                total_elements = len(interactive_elements)
                if total_elements > 30:
                    shown_elements = interactive_elements[:30]
                else:
                    shown_elements = interactive_elements
                elements_summary = "\n".join(
                    f"- `{el.get('selector', 'el')}` | tag={el.get('tag', '?')} type={el.get('type', '')} | text={el.get('text', '')[:60]}"
                    for el in shown_elements
                )
                if total_elements > 30:
                    elements_summary += f"\n\n... ({total_elements - 30} more elements)"
            except Exception as fallback_exc:
                logger.warning(
                    "Legacy JS fallback also failed: %s. No interactive elements available.",
                    fallback_exc,
                    exc_info=True,
                )
                total_elements = 0
                elements_summary = "(could not retrieve elements)"

        try:
            network_count = await self.browser_manager.get_pending_network_count()
        except Exception:
            network_count = 0

        return {
            "url": url,
            "title": title,
            "visible_text": visible_text,
            "interactive_elements": elements_summary,
            "total_elements": total_elements,
            "network_count": network_count,
        }

    def _flatten_accessibility_nodes(
        self, node: dict[str, Any] | list[dict[str, Any]], nodes: list[dict[str, Any]]
    ) -> None:
        """Flatten accessibility tree into a list (for @e indexing).

        Accepts both a dict tree (legacy / nested) and a flat list
        (browser_manager.get_accessibility_tree returns a flat list).
        """
        if not node:
            return
        if isinstance(node, list):
            # Already flat — extend directly
            nodes.extend(node)
            return
        children = node.get("children", [])
        node_copy = {k: v for k, v in node.items() if k != "children"}
        nodes.append(node_copy)
        for child in children:
            self._flatten_accessibility_nodes(child, nodes)

    def _format_observation(self, observation: dict[str, Any]) -> str:
        lines = [
            "--- Page Observation ---",
            f"URL: {observation['url']}",
            f"Title: {observation['title']}",
            f"Pending network requests: {observation['network_count']}",
            "",
            "Visible text:",
            observation["visible_text"],
            "",
            "Interactive elements (prefer @e refs when available; fallback to CSS selectors or text):",
            observation["interactive_elements"],
            "",
            "What would you like to do next? Respond with a JSON code block.",
        ]
        return "\n".join(lines)

    def _parse_response(self, response_text: str) -> dict[str, Any] | None:
        """Extract JSON from markdown code block or raw text."""
        if not response_text:
            return None
        # Try fenced code block first
        match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if not match:
            # Try any fenced block
            match = re.search(r"```\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if not match:
            # Try raw JSON object
            match = re.search(r"(\{.*\})", response_text, re.DOTALL)
        json_str = match.group(1) if match else response_text.strip()
        try:
            return cast(dict[str, Any], json.loads(json_str))
        except json.JSONDecodeError:
            return None

    async def _execute_tool(self, tool_name: str, params: dict[str, Any]) -> str:
        """Map tool_name to browser_manager method and execute with @e ref and fallback support."""
        bm = self.browser_manager
        try:
            if tool_name == "browser_navigate":
                url = params.get("url", "")
                return await bm.navigate(url)
            elif tool_name == "browser_click":
                selector = params.get("selector", "")
                by = params.get("by", "css")
                if not selector:
                    return "Error: 'selector' parameter required for browser_click"
                if selector.startswith("@e") or by == "ref":
                    result = await bm.click(selector, by="ref")
                    self.scratchpad += f"\n[Fallback] Used @e ref for click: {selector}"
                    return result
                return await bm.click(selector, by)
            elif tool_name == "browser_type":
                selector = params.get("selector", "")
                text = params.get("text", "")
                clear = params.get("clear", True)
                by = params.get("by", "css")
                if not selector:
                    return "Error: 'selector' parameter required for browser_type"
                if selector.startswith("@e") or by == "ref":
                    result = await bm.type_text(selector, text, clear, by="ref")
                    self.scratchpad += f"\n[Fallback] Used @e ref for type_text: {selector}"
                    return result
                return await bm.type_text(selector, text, clear)
            elif tool_name == "browser_select_option":
                selector = params.get("selector", "")
                value = params.get("value", "")
                if not selector:
                    return "Error: 'selector' parameter required for browser_select_option"
                # Fallback: try @e ref first, then css, then text
                result, method_used = await self._try_select_with_fallback(bm, selector, value)
                self.scratchpad += f"\n[Fallback] browser_select_option used method: {method_used}"
                return result
            elif tool_name == "browser_screenshot":
                filename = params.get("filename")
                full_page = params.get("full_page", False)
                if filename:
                    path = os.path.join(self.output_dir, filename)
                else:
                    path = os.path.join(self.output_dir, f"screenshot_{int(time.time() * 1000)}.png")
                result = await bm.screenshot(path, full_page)
                self.screenshots.append(result)
                return f"Screenshot saved to {result}"
            elif tool_name == "browser_get_content":
                selector = params.get("selector")
                as_html = params.get("as_html", False)
                return await bm.get_content(selector, as_html)
            elif tool_name == "browser_execute_javascript":
                code = params.get("code", "")
                return await bm.execute_javascript(code)
            elif tool_name == "browser_get_attributes":
                selector = params.get("selector", "")
                attribute = params.get("attribute")
                if not selector:
                    return "Error: 'selector' parameter required for browser_get_attributes"
                return await bm.get_attributes(selector, attribute)
            elif tool_name == "browser_get_network_log":
                filter_url = params.get("filter_url")
                filter_method = params.get("filter_method")
                return await bm.get_network_log(filter_url, filter_method)
            elif tool_name == "browser_export_har":
                path = params.get("path", os.path.join(self.output_dir, "network.har"))
                return await bm.export_har(path)
            elif tool_name == "browser_manage_session":
                action = params.get("action", "")
                # Pop action and remaining kwargs
                session_params = dict(params)
                session_params.pop("action", None)
                return await bm.manage_session(action, **session_params)
            elif tool_name == "browser_wait":
                condition = params.get("condition", "timeout")
                selector = params.get("selector")
                timeout = params.get("timeout")
                return await bm.wait(condition, selector, timeout)
            elif tool_name == "browser_go_back":
                return await bm.go_back()
            elif tool_name == "browser_go_forward":
                return await bm.go_forward()
            elif tool_name == "browser_reload":
                return await bm.reload()
            elif tool_name == "browser_hover":
                selector = params.get("selector", "")
                by = params.get("by", "css")
                if not selector:
                    return "Error: 'selector' parameter required for browser_hover"
                if selector.startswith("@e") or by == "ref":
                    locator = await bm.find_by_ref(selector)
                    if locator is None:
                        return f"Error: Ref '{selector}' not found for hover"
                    await locator.hover(timeout=30000)
                    self.scratchpad += f"\n[Fallback] Used @e ref for hover: {selector}"
                    return f"Hovered: {selector} (by=ref)"
                return await bm.hover(selector)
            elif tool_name == "browser_press_key":
                key = params.get("key", "")
                selector = params.get("selector")
                if not key:
                    return "Error: 'key' parameter required for browser_press_key"
                return await bm.press_key(key, selector)
            elif tool_name == "browser_upload_file":
                selector = params.get("selector", "")
                file_path = params.get("file_path", "")
                if not selector or not file_path:
                    return "Error: 'selector' and 'file_path' parameters required for browser_upload_file"
                return await bm.upload_file(selector, file_path)
            elif tool_name == "browser_accessibility_tree":
                tree = await bm.get_accessibility_tree()
                return json.dumps(tree, ensure_ascii=False, indent=2, default=str)
            else:
                return f"Error: Unknown tool '{tool_name}'"
        except Exception as exc:
            error_msg = f"Tool '{tool_name}' failed: {exc}"
            self.errors.append(error_msg)
            self.consecutive_errors += 1
            # Try fallback for click/type/hover if selector looks like CSS and fails
            try:
                if tool_name in ("browser_click", "browser_type", "browser_hover") and params.get("selector", "").startswith("@e"):
                    pass  # Already tried ref, don't double-fallback
                elif tool_name == "browser_click":
                    selector = params.get("selector", "")
                    fallback_result = await bm.get_by_text(selector)
                    if "Elemento encontrado" in fallback_result:
                        assert bm._page is not None
                        locator = bm._page.get_by_text(selector).first
                        await locator.click(timeout=30000)
                        self.scratchpad += f"\n[Fallback] browser_click fell back to get_by_text: '{selector}'"
                        return f"Clicked via text fallback: {selector}"
                elif tool_name == "browser_type":
                    selector = params.get("selector", "")
                    text = params.get("text", "")
                    clear = params.get("clear", True)
                    fallback_result = await bm.get_by_text(selector)
                    if "Elemento encontrado" in fallback_result:
                        assert bm._page is not None
                        locator = bm._page.get_by_text(selector).first
                        if clear:
                            await locator.fill(text, timeout=30000)
                        else:
                            await locator.type(text, timeout=30000)
                        self.scratchpad += f"\n[Fallback] browser_type fell back to get_by_text: '{selector}'"
                        return f"Typed via text fallback: {selector}"
                elif tool_name == "browser_hover":
                    selector = params.get("selector", "")
                    fallback_result = await bm.get_by_text(selector)
                    if "Elemento encontrado" in fallback_result:
                        assert bm._page is not None
                        locator = bm._page.get_by_text(selector).first
                        await locator.hover(timeout=30000)
                        self.scratchpad += f"\n[Fallback] browser_hover fell back to get_by_text: '{selector}'"
                        return f"Hovered via text fallback: {selector}"
            except Exception as fallback_exc:
                error_msg += f" | Fallback also failed: {fallback_exc}"
            return error_msg

    async def _try_select_with_fallback(
        self, bm: BrowserManager, selector: str, value: str
    ) -> tuple[str, str]:
        """Try select_option with @e ref, CSS, and text fallback. Returns (result, method_used)."""
        try:
            if selector.startswith("@e"):
                locator = await bm.find_by_ref(selector)
                if locator is not None:
                    await locator.select_option(value, timeout=30000)
                    return f"Option '{value}' selected in {selector} (by=ref)", "ref"
            # Try CSS first
            try:
                await bm.select_option(selector, value)
                return f"Option '{value}' selected in {selector} (by=css)", "css"
            except Exception:
                pass
            # Fallback to text
            assert bm._page is not None
            text_locator = bm._page.get_by_text(selector).first
            count = await text_locator.count()
            if count > 0:
                await text_locator.select_option(value, timeout=30000)
                return f"Option '{value}' selected in '{selector}' (by=text)", "text"
        except Exception as e:
            return f"Error selecting option: {e}", "failed"
        return f"Error: Could not select option '{value}' in '{selector}'", "failed"

    def _prune_messages(
        self, messages: list[dict[str, Any]], max_messages: int = 40
    ) -> list[dict[str, Any]]:
        """Keep system + first user task + most recent messages."""
        if len(messages) <= max_messages:
            return messages

        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # Keep first user message (task prompt) and the most recent ones
        if len(non_system) > max_messages - len(system_msgs):
            kept_user = [non_system[0]] if non_system else []
            recent = non_system[-(max_messages - len(system_msgs) - len(kept_user)):]
            # Avoid duplicating if first is already in recent
            if kept_user and kept_user[0] in recent:
                kept_user = []
            non_system = kept_user + recent

        return system_msgs + non_system

    def _build_final_result(self, success: bool, report: str) -> dict[str, Any]:
        """Build the final result dictionary with all metadata."""
        return {
            "success": success,
            "report": report,
            "action_history": self.action_history,
            "screenshots": self.screenshots,
            "network_log": [],  # populated on demand if needed
            "action_count": len(self.action_history),
            "errors": self.errors,
        }

    async def _take_screenshot(self, filename: str) -> str:
        """Take a screenshot using browser_manager and return the saved path."""
        path = os.path.join(self.output_dir, filename)
        result = await self.browser_manager.screenshot(path)
        return result
