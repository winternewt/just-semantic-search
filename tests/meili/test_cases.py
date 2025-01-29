from just_semantic_search.splitter_factory import SplitterType, create_splitter
from meilisearch_python_sdk import Index
import pytest
from sentence_transformers import SentenceTransformer
from just_semantic_search.meili.rag import MeiliRAG, SearchResults
from just_semantic_search.meili.utils.services import ensure_meili_is_running
from rich.pretty import pprint
from eliot import start_action
from tests.config import *
from just_semantic_search.embeddings import EmbeddingModel, load_sentence_transformer_from_enum

from tests.meili.functions import index_folder



@pytest.fixture
def model() -> EmbeddingModel:
    return EmbeddingModel.JINA_EMBEDDINGS_V3


@pytest.fixture
def rag(model: EmbeddingModel) -> MeiliRAG:
    host = "127.0.0.1"
    port = 7700
    api_key = "fancy_master_key"
    # Create and return RAG instance with default connection settings
    rag = MeiliRAG(
        index_name="tacutopapers",
        model=model,
        host=host,
        port=port,
        api_key=api_key,
        create_index_if_not_exists=True,
        recreate_index=False,  # Don't recreate since we just created it
        init_callback = lambda rag: ensure_meili_is_running(meili_service_dir, rag.host, rag.port)
    )
    stats = rag.index.get_stats()
    if stats.number_of_documents == 0:
        print("tacutopapers index is empty, filling it with the data")
        index_folder(tacutopapers_dir, rag)

    return rag


def test_rsids(rag: MeiliRAG, tell_text: bool = False, score_threshold: float = 0.75) -> SearchResults:

    transformer_model = load_sentence_transformer_from_enum(rag.model)
    expected ="""
    In particular for rs123456789 and rs123456788 as well as similar but misspelled rsids are added to the documents:
        * 10.txt contains both two times
        * 11.txt contains both one time
        * 12.txt and 13 contain only one rsid
        * 20.txt contains both wrong rsids two times
        * 21.txt contains both wrong rsids one time
        * 22.txt and 23 contain only one wrong rsid
    """
    
    with start_action(action_type="test_rsids") as action:
        results: SearchResults = rag.search("rs123456789 and rs123456788", model=transformer_model)
        hits = [hit for hit in results.hits if hit["_rankingScore"] >= score_threshold]
        texts = [hit["text"] for hit in hits]
        sources = [hit["source"] for hit in hits]
        sources_last_part = [source.split("/")[-1] for source in sources]

        scores = [hit["_rankingScore"] for hit in hits]
        fields = results.hits[0].keys()
        print('first hit:' , fields)
        pprint(results.hits[0]["source"])
        scored_sources = [{"source": source, "score": score} for source, score in zip(sources, scores)]
        assert "10.txt" in sources_last_part[:2] , "10.txt contains both two times"
        assert "11.txt" in sources_last_part[:2] , "11.txt contains both two times"
        assert "12.txt" in sources_last_part[3:5] , "12.txt contains only one rsid"
            
        action.add_success_fields(
            message_type="test_rsids_complete",
            sources=scored_sources,
            texts=texts if tell_text else None,
            count=len(hits),
            expected=expected,
            semantic_hit_count=results.semantic_hit_count,
            score_threshold=score_threshold
        )

        return results
    

def test_superhero_search(rag: MeiliRAG, tell_text: bool = False, score_threshold: float = 0.75) -> SearchResults:
    transformer_model = load_sentence_transformer_from_enum(rag.model)
    with start_action(action_type="test_superhero_search") as action:
        results = rag.search("comic superheroes", model=transformer_model)
      
        hits = [hit for hit in results.hits if hit["_rankingScore"] >= score_threshold]
        texts = [hit["text"] for hit in hits]
        sources = [hit["source"] for hit in hits]
        sources_last_part = [source.split("/")[-1] for source in sources]
        scores = [hit["_rankingScore"] for hit in hits]
        
        print('first hit:')
        pprint(results.hits[0])
        scored_sources = [{"source": source, "score": score} for source, score in zip(sources, scores)]
        assert "114.txt" in sources_last_part[0], "Only 114 document has text about superheroes, but text did not contain words 'comics' or 'superheroes'"
        
        action.add_success_fields(
            message_type="test_superhero_search",
            sources=scored_sources,
            texts=texts if tell_text else None,
            count=len(hits),
            semantic_hit_count=results.semantic_hit_count,
        )
        return results