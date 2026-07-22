from transformers import BartTokenizer

from models.hf_base import HFBase


class BART(HFBase):
    def __init__(self,config):
        super().__init__(config)
        self.model_name = 'bart'
        self.token_type_ids_disable = True

    def get_tokenizer(self):
        tokenizer = BartTokenizer.from_pretrained(self.model_dir)
        return tokenizer
