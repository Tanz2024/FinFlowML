import time
from dataclasses import dataclass
from typing import Any

MODEL_ID = "Qwen/Qwen3-4B-Instruct-2507"


@dataclass
class BaselineModel:
    model: Any
    tokenizer: Any
    device: str
    dtype: str
    revision: str | None

    @classmethod
    def load(cls, model_id: str = MODEL_ID) -> "BaselineModel":
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        if torch.backends.mps.is_available():
            device, dtype = "mps", torch.float16
        elif torch.cuda.is_available():
            device, dtype = "cuda", torch.bfloat16
        else:
            device, dtype = "cpu", torch.float32
        tokenizer = AutoTokenizer.from_pretrained(model_id)
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype)
        model.to(device).eval()
        revision = getattr(model.config, "_commit_hash", None)
        return cls(model, tokenizer, device, str(dtype), revision)

    def generate(self, prompt: str, max_new_tokens: int = 128) -> tuple[str, float]:
        import torch

        messages = [{"role": "user", "content": prompt}]
        rendered = self.tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)
        inputs = self.tokenizer(rendered, return_tensors="pt").to(self.device)
        started = time.perf_counter()
        with torch.inference_mode():
            output = self.model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
        elapsed = time.perf_counter() - started
        generated = output[0][inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(generated, skip_special_tokens=True), elapsed
