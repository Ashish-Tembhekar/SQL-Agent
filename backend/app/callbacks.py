from langchain_core.callbacks import BaseCallbackHandler
import threading


class StreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self):
        self.full_response = ""
        self.tool_calls = []
        self.tool_results = []
        self._lock = threading.Lock()

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        with self._lock:
            self.full_response += token

    def on_llm_end(self, response, **kwargs):
        pass

    def on_tool_start(self, serialized, input_str, **kwargs):
        with self._lock:
            self.tool_calls.append({
                "tool": serialized.get("name", "unknown"),
                "input": input_str,
            })

    def on_tool_end(self, output, **kwargs):
        with self._lock:
            self.tool_results.append({
                "output": str(output)[:500],
            })

    def on_llm_error(self, error, **kwargs):
        pass

    def on_tool_error(self, error, **kwargs):
        pass

    def get_response(self) -> str:
        with self._lock:
            return self.full_response

    def get_tool_calls(self) -> list:
        with self._lock:
            return list(self.tool_calls)

    def get_tool_results(self) -> list:
        with self._lock:
            return list(self.tool_results)
