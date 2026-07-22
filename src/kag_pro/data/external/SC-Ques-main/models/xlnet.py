from transformers import (
    AutoTokenizer,
)

from models.hf_base import HFBase


class XLNet(HFBase):
    def __init__(self,config):
        super().__init__(config)
        self.model_name = 'xlnet'

    def get_tokenizer(self):
        tokenizer = AutoTokenizer.from_pretrained(self.model_dir)
        return tokenizer
