import json
import threading
from kitchen_commands import PROMPT, SCHEMA


class ToolSelector:
    def __init__(self, path):
        self.path = str(path)
        self.model = None
        self.lock = threading.Lock()

    def infer(self, data):
        content = data.get('user_content')
        history = data.get('history', [])
        if not isinstance(content,str) or len(content)>6000 or not isinstance(history,list) or len(history)>4:
            raise ValueError('명령 길이 오류')
        if any(not isinstance(m,dict) or m.get('role') not in ('user','assistant') or
               not isinstance(m.get('content'),str) or len(m['content'])>300 for m in history):
            raise ValueError('이전 명령 형식 오류')
        with self.lock:
            if self.model is None:
                from llama_cpp import Llama
                self.model = Llama(model_path=self.path, n_ctx=4096, n_threads=4, verbose=False)
            result = self.model.create_chat_completion(
                messages=[{'role':'system','content':PROMPT}, *history, {'role':'user','content':content+' /no_think'}],
                response_format={'type':'json_object','schema':SCHEMA}, temperature=0, max_tokens=220)
        return json.loads(result['choices'][0]['message']['content'])
