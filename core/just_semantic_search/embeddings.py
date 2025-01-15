import typer
from sentence_transformers import SentenceTransformer
from pprint import pprint
from transformers import AutoTokenizer, AutoModel, PreTrainedModel, PreTrainedTokenizer
from typing import Tuple, Union, Any
from enum import Enum

def load_auto_model_tokenizer(model_name_or_path: str, trust_remote_code: bool = True) -> Tuple[PreTrainedModel, PreTrainedTokenizer]:
    model = AutoModel.from_pretrained(model_name_or_path, trust_remote_code=trust_remote_code)
    tokenizer = AutoTokenizer.from_pretrained(model_name_or_path, trust_remote_code=trust_remote_code)
    return model, tokenizer

def load_sentence_transformer_model(model_name_or_path: str) -> SentenceTransformer:
    model = SentenceTransformer(model_name_or_path, trust_remote_code=True)
    return model

class EmbeddingModel(Enum):
    GTE_LARGE = "Alibaba-NLP/gte-large-en-v1.5"
    GTE_MULTILINGUAL = "Alibaba-NLP/gte-multilingual-base"
    GTE_MULTILINGUAL_MLM = "Alibaba-NLP/gte-multilingual-mlm-base"
    GTE_MLM_EN = "Alibaba-NLP/gte-en-mlm-large"
    SPECTER = "sentence-transformers/allenai-specter"
    BIOEMBEDDINGS = "pavanmantha/bge-base-en-bioembed"
    MODERN_BERT_LARGE = "answerdotai/ModernBERT-large"
    JINA_EMBEDDINGS_V3 = "jinaai/jina-embeddings-v3"
    MEDCPT_QUERY = "ncbi/MedCPT-Query-Encoder"
    MEDCPT_ARTICLE = "MedCPT-Article-Encoder"
    
    @classmethod
    def OTHER(cls, model_path: str) -> 'EmbeddingModel':
        """Create a custom EmbeddingModel instance with an arbitrary model path"""
        # Create a new enum member dynamically
        other = object.__new__(cls)
        other._value_ = model_path
        other._name_ = f"OTHER_{model_path.replace('/', '_')}"
        return other

def load_model_from_enum(model: EmbeddingModel) -> Union[SentenceTransformer, Tuple[PreTrainedModel, PreTrainedTokenizer]]:
    """
    Factory function to load a model based on the EmbeddingModel enum
    """
    if model in [EmbeddingModel.MEDCPT_QUERY, EmbeddingModel.MEDCPT_ARTICLE]:
        return load_auto_model_tokenizer(model.value)
    return load_sentence_transformer_model(model.value)

def load_sentence_transformer_from_enum(model: EmbeddingModel) -> SentenceTransformer:
    """
    Factory function to load only SentenceTransformer models based on the EmbeddingModel enum.
    Raises ValueError if the model is not compatible with SentenceTransformer.
    """
    if model in [EmbeddingModel.MEDCPT_QUERY, EmbeddingModel.MEDCPT_ARTICLE]:
        raise ValueError(f"{model.name} is not compatible with SentenceTransformer")
    return load_sentence_transformer_model(model.value)

# You can now replace the individual loading functions with this more elegant solution
# or keep them as convenience functions that use the enum internally

