from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrainingConfig:
    model_id: str = "Qwen/Qwen3-4B-Instruct-2507"
    model_revision: str = "cdbee75f17c01a7cc42f958dc650907174af0554"
    dataset_id: str = "mp-02/sroie"
    seed: int = 42
    max_seq_length: int = 2048
    learning_rate: float = 2e-4
    train_batch_size: int = 1
    gradient_accumulation_steps: int = 16
    epochs: int = 3
    warmup_ratio: float = 0.05
    scheduler: str = "cosine"
    gradient_checkpointing: bool = True
    packing: bool = False
    optimizer: str = "paged_adamw_8bit"
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: tuple[str, ...] = field(default_factory=lambda: ("q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"))
    output_dir: str = "results/stage4"
    smoke_train_examples: int = 12
    smoke_steps: int = 4

    def validate(self) -> None:
        if self.max_seq_length <= 0 or self.train_batch_size != 1:
            raise ValueError("max_seq_length must be positive and train_batch_size must be 1")
        if self.optimizer != "paged_adamw_8bit" or self.packing:
            raise ValueError("Stage 4 requires paged_adamw_8bit and packing=False")
        if not self.target_modules:
            raise ValueError("At least one LoRA target module is required")
        if self.smoke_train_examples <= 0 or self.smoke_steps <= 0:
            raise ValueError("smoke_train_examples and smoke_steps must be positive")
