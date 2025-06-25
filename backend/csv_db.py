import pandas as pd
import numpy as np
import os
import logging
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
import uuid
from datetime import datetime
import json
from typing import List, Dict, Optional
import glob
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CSVToVectorDB:
    """
    Convert RBI and SEBI scraped CSV files to Vector Database for RAG pipeline
    """
    def __init__(
        self,
        csv_folders: list = None,
        vector_db_path: str = "./financial_vector_db",
        embedding_model: str = "all-MiniLM-L6-v2",
        collection_name: str = "financial_documents"
    ):
        """
        Initialize the CSV to Vector DB converter

        Args:
            csv_folders: List of folders containing CSV files (default: ['./', './rbi_news_results', './sebi_news_results'])
            vector_db_path: Path where vector database will be stored
            embedding_model: Sentence transformer model name
            collection_name: Name of the ChromaDB collection
        """
        if csv_folders is None:
            csv_folders = ["./", "./rbi_news_scraper_results", "./sebi_news_scraper_results"]
        self.csv_folders = csv_folders
        self.vector_db_path = vector_db_path
        self.embedding_model_name = embedding_model
        self.collection_name = collection_name
        
        # Initialize embedding model
        logger.info(f"Loading embedding model: {embedding_model}")
        self.embedding_model = SentenceTransformer(embedding_model)
        
        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=vector_db_path,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Get or create collection
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "RBI and SEBI Documents from scraped data"}
        )
        
        logger.info(f"Vector database initialized at: {vector_db_path}")
        logger.info(f"Collection name: {collection_name}")
    
    def find_csv_files(self) -> Dict[str, List[str]]:
        """
        Find all CSV files from both RBI and SEBI scrapers in all relevant folders

        Returns:
            Dictionary with RBI and SEBI CSV files
        """
        csv_files = {'rbi': [], 'sebi': []}

        # Patterns for RBI and SEBI CSVs
        rbi_patterns = [
            "*rbi_news_scraper_results*.csv",
            "*rbi_news_topic*.csv"
        ]
        sebi_patterns = [
            "*sebi_news_topic*.csv"
        ]

        # Search in all folders
        for folder in self.csv_folders:
            for pattern in rbi_patterns:
                found = glob.glob(os.path.join(folder, pattern))
                found = [f for f in found if '_summary.csv' not in f]
                csv_files['rbi'].extend(found)
            for pattern in sebi_patterns:
                found = glob.glob(os.path.join(folder, pattern))
                found = [f for f in found if '_summary.csv' not in f]
                csv_files['sebi'].extend(found)

        # Remove duplicates
        csv_files['rbi'] = list(set(csv_files['rbi']))
        csv_files['sebi'] = list(set(csv_files['sebi']))

        logger.info(f"Found {len(csv_files['rbi'])} RBI CSV files: {[os.path.basename(f) for f in csv_files['rbi']]}")
        logger.info(f"Found {len(csv_files['sebi'])} SEBI CSV files: {[os.path.basename(f) for f in csv_files['sebi']]}")

        return csv_files
    
    def detect_source_type(self, csv_file: str) -> str:
        """
        Detect if CSV file is from RBI or SEBI based on filename and path
        
        Args:
            csv_file: Path to CSV file
            
        Returns:
            'rbi' or 'sebi'
        """
        file_path = csv_file.lower()
        
        if 'rbi' in file_path or 'rbi_news_results' in file_path:
            return 'rbi'
        elif 'sebi' in file_path or 'sebi_news_results' in file_path:
            return 'sebi'
        else:
            # Try to detect from content structure
            try:
                df = pd.read_csv(csv_file, nrows=1)
                # RBI files typically have these columns
                if any(col in df.columns for col in ['news_topic', 'max_similarity']):
                    return 'rbi'
                else:
                    return 'sebi'
            except:
                logger.warning(f"Could not detect source type for {csv_file}, defaulting to 'rbi'")
                return 'rbi'
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for better embedding
        
        Args:
            text: Input text to chunk
            chunk_size: Maximum size of each chunk
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text or len(text) < chunk_size:
            return [text] if text else []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for punct in ['. ', '.\n', '! ', '!\n', '? ', '?\n']:
                    punct_pos = text.rfind(punct, start, end)
                    if punct_pos > start + chunk_size // 2:  # Don't make chunks too small
                        end = punct_pos + len(punct)
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            
        return chunks
    
    def process_csv_file(self, csv_file: str) -> List[Dict]:
        """
        Process a single CSV file and prepare documents for vector DB
        
        Args:
            csv_file: Path to CSV file
            
        Returns:
            List of document dictionaries
        """
        logger.info(f"Processing CSV file: {os.path.basename(csv_file)}")
        
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
            logger.info(f"Loaded {len(df)} rows from CSV")
            
            source_type = self.detect_source_type(csv_file)
            documents = []
            
            for idx, row in df.iterrows():
                try:
                    # Extract basic information
                    title = str(row.get('title', 'Untitled')).strip()
                    content = str(row.get('content', '')).strip()
                    date = str(row.get('date', 'N/A')).strip()
                    pdf_url = str(row.get('pdf_url', '')).strip()
                    
                    if not content or content == 'nan':
                        logger.warning(f"Skipping row {idx}: No content")
                        continue
                    
                    # Create chunks from content
                    chunks = self.chunk_text(content)
                    
                    for chunk_idx, chunk in enumerate(chunks):
                        if not chunk.strip():
                            continue
                        
                        # Create document metadata
                        metadata = {
                            'source_type': source_type.upper(),  # RBI or SEBI
                            'source_file': os.path.basename(csv_file),
                            'document_id': f"{source_type}_{os.path.basename(csv_file)}_{idx}",
                            'chunk_id': f"{source_type}_{os.path.basename(csv_file)}_{idx}_{chunk_idx}",
                            'title': title,
                            'date': date,
                            'pdf_url': pdf_url,
                            'chunk_index': chunk_idx,
                            'total_chunks': len(chunks),
                            'content_length': len(chunk),
                            'processed_at': datetime.now().isoformat(),
                        }
                        
                        # Add source-specific metadata if available
                        if source_type == 'rbi':
                            for col in ['news_topic', 'max_similarity', 'all_found_terms', 'terms_count']:
                                if col in row and pd.notna(row[col]):
                                    metadata[col] = str(row[col])
                        elif source_type == 'sebi':
                            # Add SEBI-specific columns if they exist
                            for col in ['category', 'regulation', 'circular_type']:
                                if col in row and pd.notna(row[col]):
                                    metadata[col] = str(row[col])
                        
                        # Also include any other columns that might be present
                        for col in df.columns:
                            if col not in ['title', 'content', 'date', 'pdf_url'] and col not in metadata:
                                if pd.notna(row[col]):
                                    metadata[col] = str(row[col])
                        
                        # Create combined text for embedding (title + content)
                        combined_text = f"Source: {source_type.upper()}\nTitle: {title}\n\nContent: {chunk}"
                        
                        documents.append({
                            'id': str(uuid.uuid4()),
                            'text': combined_text,
                            'chunk_content': chunk,
                            'metadata': metadata
                        })
                        
                except Exception as e:
                    logger.error(f"Error processing row {idx}: {e}")
                    continue
            
            logger.info(f"Created {len(documents)} document chunks from {os.path.basename(csv_file)}")
            return documents
            
        except Exception as e:
            logger.error(f"Error processing CSV file {csv_file}: {e}")
            return []
    
    def create_embeddings(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Create embeddings for texts in batches
        
        Args:
            texts: List of texts to embed
            batch_size: Batch size for embedding generation
            
        Returns:
            Numpy array of embeddings
        """
        logger.info(f"Creating embeddings for {len(texts)} texts...")
        
        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_embeddings = self.embedding_model.encode(
                batch,
                convert_to_numpy=True,
                show_progress_bar=True if i == 0 else False
            )
            embeddings.append(batch_embeddings)
        
        embeddings = np.vstack(embeddings)
        logger.info(f"Created embeddings with shape: {embeddings.shape}")
        return embeddings
    
    def add_documents_to_collection(self, documents: List[Dict]):
        """
        Add documents to ChromaDB collection
        
        Args:
            documents: List of document dictionaries
        """
        if not documents:
            logger.warning("No documents to add")
            return
        
        logger.info(f"Adding {len(documents)} documents to vector database...")
        
        # Prepare data for ChromaDB
        ids = [doc['id'] for doc in documents]
        texts = [doc['text'] for doc in documents]
        metadatas = [doc['metadata'] for doc in documents]
        
        # Create embeddings
        embeddings = self.create_embeddings(texts)
        
        # Add to collection in batches
        batch_size = 100
        for i in range(0, len(documents), batch_size):
            end_idx = min(i + batch_size, len(documents))
            
            self.collection.add(
                ids=ids[i:end_idx],
                documents=texts[i:end_idx],
                embeddings=embeddings[i:end_idx].tolist(),
                metadatas=metadatas[i:end_idx]
            )
            
            logger.info(f"Added batch {i//batch_size + 1}/{(len(documents)-1)//batch_size + 1}")
        
        logger.info(f"Successfully added {len(documents)} documents to collection")
    
    def process_all_csv_files(self):
        """
        Process all CSV files from both RBI and SEBI and create vector database
        """
        logger.info("Starting CSV to Vector DB conversion process...")
        
        # Find CSV files
        csv_files = self.find_csv_files()
        
        total_files = len(csv_files['rbi']) + len(csv_files['sebi'])
        if total_files == 0:
            logger.error("No CSV files found")
            return
        
        # Process each CSV file
        all_documents = []
        
        # Process RBI files
        for csv_file in csv_files['rbi']:
            documents = self.process_csv_file(csv_file)
            all_documents.extend(documents)
        
        # Process SEBI files
        for csv_file in csv_files['sebi']:
            documents = self.process_csv_file(csv_file)
            all_documents.extend(documents)
        
        if not all_documents:
            logger.error("No documents were processed from CSV files")
            return
        
        # Add documents to vector database
        self.add_documents_to_collection(all_documents)
        
        # Save processing summary
        self.save_processing_summary(csv_files, all_documents)
        
        logger.info("CSV to Vector DB conversion completed successfully!")
    
    def save_processing_summary(self, csv_files: Dict[str, List[str]], documents: List[Dict]):
        """
        Save a summary of the processing
        
        Args:
            csv_files: Dictionary of processed CSV files by source
            documents: List of processed documents
        """
        summary = {
            'processing_date': datetime.now().isoformat(),
            'rbi_files_processed': [os.path.basename(f) for f in csv_files['rbi']],
            'sebi_files_processed': [os.path.basename(f) for f in csv_files['sebi']],
            'total_files_processed': len(csv_files['rbi']) + len(csv_files['sebi']),
            'total_documents': len(documents),
            'embedding_model': self.embedding_model_name,
            'vector_db_path': self.vector_db_path,
            'collection_name': self.collection_name,
            'documents_by_source_type': {},
            'documents_by_source_file': {}
        }
        
        # Count documents by source type and file
        for doc in documents:
            source_type = doc['metadata']['source_type']
            source_file = doc['metadata']['source_file']
            
            summary['documents_by_source_type'][source_type] = summary['documents_by_source_type'].get(source_type, 0) + 1
            summary['documents_by_source_file'][source_file] = summary['documents_by_source_file'].get(source_file, 0) + 1
        
        # Save summary
        summary_path = os.path.join(self.vector_db_path, 'processing_summary.json')
        os.makedirs(os.path.dirname(summary_path), exist_ok=True)
        
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Processing summary saved to: {summary_path}")
    
    
    def get_collection_stats(self) -> Dict:
        """
        Get statistics about the vector database collection
        
        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()
        
        # Get a sample of documents to analyze
        sample = self.collection.peek(limit=min(100, count))
        
        sources = set()
        source_types = set()
        topics = set()
        
        if sample['metadatas']:
            for metadata in sample['metadatas']:
                if 'source_file' in metadata:
                    sources.add(metadata['source_file'])
                if 'source_type' in metadata:
                    source_types.add(metadata['source_type'])
                if 'news_topic' in metadata:
                    topics.add(metadata['news_topic'])
        
        return {
            'total_documents': count,
            'collection_name': self.collection_name,
            'source_types': list(source_types),
            'unique_source_files': len(sources),
            'sample_source_files': list(sources)[:5],
            'unique_topics': len(topics),
            'sample_topics': list(topics)[:5],  # Show first 5 topics
            'embedding_model': self.embedding_model_name,
            'vector_db_path': self.vector_db_path
        }

# Example usage function (optional)
def run_vector_db_conversion():
    """
    Standalone function to run the CSV to Vector DB conversion
    Can be called from other scripts
    """
    # Configuration
    config = {
        'csv_folder': "./",  # Current directory where CSV files are located
        'vector_db_path': "./financial_vector_db",  # Where to store the vector database
        'embedding_model': "all-MiniLM-L6-v2",  # Embedding model
        'collection_name': "financial_documents"  # ChromaDB collection name
    }
    
    # Initialize converter
    converter = CSVToVectorDB(
        csv_folder=config['csv_folder'],
        vector_db_path=config['vector_db_path'],
        embedding_model=config['embedding_model'],
        collection_name=config['collection_name']
    )
    
    # Process all CSV files
    converter.process_all_csv_files()
    
    # Show statistics
    stats = converter.get_collection_stats()
    logger.info("=== Vector Database Statistics ===")
    for key, value in stats.items():
        logger.info(f"{key}: {value}")
    
    return converter

# Only run if this file is executed directly (not imported)
if __name__ == "__main__":
    run_vector_db_conversion()