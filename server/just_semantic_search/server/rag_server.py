from functools import cached_property
import os
from typing import List, Dict, Optional
from dotenv import load_dotenv
from just_semantic_search.embeddings import EmbeddingModel
from just_semantic_search.meili.tools import search_documents, all_indexes
from just_semantic_search.server.rag_agent import default_annotation_agent, default_rag_agent
from pydantic import BaseModel, Field
from just_agents.base_agent import BaseAgent
from just_agents.web.chat_ui_rest_api import ChatUIAgentRestAPI, ChatUIAgentConfig
from eliot import start_task
from pathlib import Path
import typer
import uvicorn
from just_semantic_search.server.indexing import Indexing
from pathlib import Path


class RAGServerConfig(ChatUIAgentConfig):
    """Configuration for the RAG server"""

    
    host: str = Field(
        default_factory=lambda: os.getenv("APP_HOST", "0.0.0.0").split()[0],
        description="Host address to bind the server to",
        examples=["0.0.0.0", "127.0.0.1"]
    )

    embedding_model: EmbeddingModel = Field(
        default=EmbeddingModel.JINA_EMBEDDINGS_V3,
        description="Embedding model to use"
    )

    def set_general_port(self, port: int):
        self.agent_port = port
        self.port = port



class SearchRequest(BaseModel):
    """Request model for basic semantic search"""
    query: str = Field(example="Glucose predictions models for CGM")
    index: str = Field(example="glucosedao")
    limit: int = Field(default=10, ge=1, example=30)
    semantic_ratio: float = Field(default=0.5, ge=0.0, le=1.0, example=0.5)
   

class SearchAgentRequest(BaseModel):
    """Request model for RAG-based advanced search"""
    query: str = Field(example="Glucose predictions models for CGM")
    index: Optional[str] = Field(default=None, example="glucosedao")
    additional_instructions: Optional[str] = Field(default=None, example="You must always provide quotes from evidence followed by the sources (not in the end but immediately after the quote)")

class RAGServer(ChatUIAgentRestAPI):
    """Extended REST API implementation that adds RAG (Retrieval-Augmented Generation) capabilities"""

    indexing: Indexing

    @cached_property
    def rag_agent(self):
        if "rag_agent" in self.agents:
            return self.agents["rag_agent"]
        elif "default" in self.agents:
            return self.agents["default"]
        else:
            raise ValueError("RAG agent not found")

    @cached_property
    def annotation_agent(self):
        if "annotation_agent" in self.agents:
            return self.agents["annotation_agent"]
        elif "annotator" in self.agents:
            return self.agents["annotator"]
        else:
            raise ValueError("Annotation agent not found")


    def __init__(self, 
                 agents: Optional[Dict[str, BaseAgent]] = None,
                 agent_profiles: Optional[Path | str] = None,
                 agent_section: Optional[str] = None,
                 agent_parent_section: Optional[str] = None,
                 debug: bool = False,
                 title: str = "Just-Agent endpoint",
                 description: str = "OpenAI-compatible API endpoint for Just-Agents",
                 config: Optional[RAGServerConfig] = None,
                 *args, **kwargs):
        if agents is not None:
            kwargs["agents"] = agents

        self.config = RAGServerConfig() if config is None else config
        super().__init__(
            agent_config=agent_profiles,
            agent_section=agent_section,
            agent_parent_section=agent_parent_section,
            debug=debug,
            title=title,
            description=description,
            *args, **kwargs
        )
        self.indexing = Indexing(
            annotation_agent=self.annotation_agent,
            embedding_model=config.embedding_model
        )
        self._indexes = None
        self._configure_rag_routes()
        
    def _prepare_model_jsons(self):
        with start_task(action_type="rag_server_prepare_model_jsons") as action:
            action.log("PREPARING MODEL JSONS!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            super()._prepare_model_jsons()
        
    def _initialize_config(self):
        """Overriding initialization from config"""
        with start_task(action_type="rag_server_initialize_config") as action:
            action.log(f"Config: {self.config}")
            if Path(self.config.env_keys_path).resolve().absolute().exists():
                load_dotenv(self.config.env_keys_path, override=True)
            if not Path(self.config.models_dir).exists():
                action.log(f"Creating models directory {self.config.models_dir} which does not exist")
                Path(self.config.models_dir).mkdir(parents=True, exist_ok=True)
            if "env/" in self.config.env_models_path:
                if not Path("env").exists():
                    action.log(f"Creating env directory {self.config.env_models_path} which does not exist")
                    Path("env").mkdir(parents=True, exist_ok=True)
            
                    

    @property
    def indexes(self) -> List[str]:
        """Lazy property that returns cached list of indexes or fetches them if not cached"""
        if self._indexes is None:
            self._indexes = self.list_indexes()
        return self._indexes
    

    def _configure_rag_routes(self):
        """Configure RAG-specific routes"""
        # Add a check to prevent duplicate route registration
        route_paths = [route.path for route in self.routes]
        
        if "/search" not in route_paths:
            self.post("/search", description="Perform semantic search")(self.search)
        
        if "/search_agent" not in route_paths:
            self.post("/search_agent", description="Perform advanced RAG-based search")(self.search_agent)
        
        if "/list_indexes" not in route_paths:
            self.post("/list_indexes", description="Get all indexes")(self.list_indexes)
        
        if "/index_markdown_folder" not in route_paths:
            self.post("/index_markdown_folder", description="Index a folder with markdown files")(self.indexing.index_markdown_folder)


    

    def search(self, request: SearchRequest) -> list[str]:
        """
        Perform a semantic search.
        
        Args:
            request: SearchRequest object containing search parameters
            
        Returns:
            List of matching documents with their metadata
        """
        with start_task(action_type="rag_server_search", 
                       query=request.query, 
                       index=request.index, 
                       limit=request.limit) as action:
            action.log("performing search")
            return search_documents(
                query=request.query,
                index=request.index,
                limit=request.limit,
                semantic_ratio=request.semantic_ratio
            )

    def search_agent(self, request: SearchAgentRequest) -> str:
        """
        Perform an advanced search using the RAG agent that can provide contextual answers.
        
        Args:
            request: SearchAgentRequest object containing the query, optional index, and additional instructions
            
        Returns:
            A detailed response from the RAG agent incorporating retrieved documents
        """

        with start_task(action_type="rag_server_advanced_search", query=request.query) as action:
            import uuid
            request_id = str(uuid.uuid4())[:8]
            action.log(f"[{request_id}] Received search_agent request")
            
            indexes = self.indexes if request.index is None else [request.index]
            query = f"Search the following query:```\n{request.query}\n```\nYou can only search in the following indexes: {indexes}"
            if request.additional_instructions is not None:
                query += f"\nADDITIONAL INSTRUCTIONS: {request.additional_instructions}"
            
            action.log(f"[{request_id}] Querying RAG agent")
            result = self.rag_agent.query(query)
            action.log(f"[{request_id}] Completed search_agent request")
            return result
    
    def list_indexes(self, non_empty: bool = True) -> List[str]:
        """
        Get all indexes and update the cache.
        """
        self._indexes = all_indexes(non_empty=non_empty)
        return self._indexes
    
    

def run_rag_server(
    agent_profiles: Optional[Path] = None,
    host: str = "0.0.0.0",
    port: int = 8091,
    workers: int = 1,
    title: str = "Just-Agent endpoint",
    section: Optional[str] = None,
    parent_section: Optional[str] = None,
    debug: bool = True,
    agents: Optional[Dict[str, BaseAgent]] = None
) -> None:
    """Run the RAG server with the given configuration."""
    # Initialize the API class with the updated configuration
    config = RAGServerConfig()
    config.set_general_port(port)

    api = RAGServer(
        agent_profiles=agent_profiles,
        agent_parent_section=parent_section,
        agent_section=section,
        debug=debug,
        title=title,
        agents=agents,
        config=config
    )
    
    uvicorn.run(
        api,
        host=host,
        port=port,
        workers=workers
    )


env_config = RAGServerConfig()
env_config.set_general_port(8091)


def run_rag_server_command(
    agent_profiles: Optional[Path] = None,
    host: str = env_config.host,
    port: int = env_config.port,
    workers: int = env_config.workers,
    title: str = env_config.title,
    section: Optional[str] = env_config.section,
    parent_section: Optional[str] = env_config.parent_section,
    debug: bool = env_config.debug,
) -> None:
    """Run the FastAPI server for RAGServer with the given configuration."""
    if agent_profiles is None:
        with start_task(action_type="rag_server_run_rag_server_command", agent_profiles=agent_profiles) as action:
            action.log("config is None, using default RAG agent")
            agents = {"rag_agent": default_rag_agent(), "annotation_agent": default_annotation_agent()}
    else:
        agents = None
    
    run_rag_server(
        agent_profiles=agent_profiles,
        host=host,
        port=port,
        workers=workers,
        title=title,
        section=section,
        parent_section=parent_section,
        debug=debug,
        agents=agents
    )
    
    

if __name__ == "__main__":
    env_config = RAGServerConfig()
    app = typer.Typer()
    app.command()(run_rag_server_command)
    app()
