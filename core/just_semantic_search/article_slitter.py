from sentence_transformers import SentenceTransformer
from typing import List, Optional
from just_semantic_search.text_splitter import AbstractSplitter
from pathlib import Path
from just_semantic_search.document import Document, ArticleDocument
# Add at the top of the file, after imports


class ArticleSplitter(AbstractSplitter[str, ArticleDocument]):
    """
    A specialized text splitter designed for processing scientific articles and research papers.
    
    This splitter creates ArticleDocument objects that maintain the document's structure with
    title, abstract, and source information. It's particularly useful for:
    - Processing academic papers and research articles
    - Maintaining document metadata (title, abstract) during splitting
    - Creating embeddings for scientific content while preserving context
    
    The splitter ensures that the resulting chunks are properly sized for the underlying
    transformer model while maintaining document attribution.
    """

    def __init__(self, model: SentenceTransformer, model_name: Optional[str] = None, write_token_counts: bool = True):
        super().__init__(model, model_name=model_name, write_token_counts=write_token_counts)
    

    def split(self, text: str, embed: bool = True, 
              title: str | None = None,
              abstract: str | None = None,
              source: str | None = None,  
              **kwargs) -> List[Document]:
        """
        Split text into chunks based on token length.
        Note: Current implementation has an undefined max_seq_length variable
        and doesn't create Document objects as specified in return type.
        """
        adjusted_max_chunk_size = ArticleDocument.calculate_adjusted_chunk_size(
                self.model.tokenizer,
                self.max_seq_length,
                title=title,
                abstract=abstract,
                source=source
            )

        # Get the tokenizer from the model
        tokenizer = self.model.tokenizer

        # Tokenize the entire text
        tokens = tokenizer.tokenize(text)

        # Combine both operations in a single loop
        text_chunks = []
        token_counts = []
        for i in range(0, len(tokens), adjusted_max_chunk_size):
            chunk = tokens[i:i + self.max_seq_length]
            text_chunks.append(tokenizer.convert_tokens_to_string(chunk))
            token_counts.append(len(chunk))
        
        # Create annotated ArticleDocument objects
        documents = []
        for i, chunk in enumerate(text_chunks):
            doc = ArticleDocument(
                text=chunk,
                title=title,
                abstract=abstract,
                source=source,
                fragment_num=i + 1,
                total_fragments=len(text_chunks),
                token_count=token_counts[i] if self.write_token_counts else None
            )
            updated_doc = doc.with_vector(self.model_name, self.model.encode(doc.content) if embed else None)
            if self.write_token_counts:
                updated_doc.token_count =len(self.tokenizer.tokenize(updated_doc.content)) 
            documents.append(updated_doc)
        
        return documents
    
    def _content_from_path(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")
    

    def split_file(self, file_path: Path | str, embed: bool = True, 
                title: str | None = None,
                abstract: str | None = None,
                source: str | None = None,  
                **kwargs) -> List[ArticleDocument]:
        if isinstance(file_path, str):
            file_path = Path(file_path)
        if source is None:
            source = str(file_path.absolute())
        content: str = self._content_from_path(file_path)
        return self.split(content, embed, title=title, abstract=abstract, source=source, **kwargs)