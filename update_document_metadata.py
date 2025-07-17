#!/usr/bin/env python3
"""
Script to update existing document metadata with product names from CSV.

This script reads the CSV file and updates existing documents in ChromaDB 
with product names and URLs based on the filename matching.

Usage:
    python update_document_metadata.py [--limit N] [--csv-file path/to/csv]
"""

import os
import csv
import logging
from pathlib import Path
from typing import Dict, List, Optional
import argparse
import chromadb

# Import config
from app import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_csv_file(csv_file_path: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """Read the CSV file and return a list of document records."""
    records = []
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                    
                record = {
                    'product_name': row.get('Product Name', '').strip(),
                    'ecopyfile': row.get('eCopyfile', '').strip(),
                    'url': row.get('CII Website URL', '').strip()
                }
                
                if not record['ecopyfile']:
                    logger.warning(f"Skipping row {i+1}: Missing eCopyfile")
                    continue
                
                records.append(record)
                
        logger.info(f"Read {len(records)} records from CSV file")
        return records
        
    except FileNotFoundError:
        logger.error(f"CSV file not found: {csv_file_path}")
        return []
    except Exception as e:
        logger.error(f"Error reading CSV file: {e}")
        return []

def update_document_metadata_from_csv(
    csv_file_path: str = "cii-urls.csv",
    limit: Optional[int] = None,
    collection_name: str = None,
    persist_dir: str = None
) -> Dict[str, int]:
    """
    Update existing document metadata with product names from CSV.
    """
    # Use config defaults if not provided
    collection_name = collection_name or config.COLLECTION_NAME
    persist_dir = persist_dir or str(config.PERSIST_DIR)
    
    logger.info(f"Starting metadata update from CSV")
    logger.info(f"CSV file: {csv_file_path}")
    logger.info(f"Collection: {collection_name}")
    logger.info(f"Limit: {limit or 'No limit'}")
    
    # Read CSV records
    records = read_csv_file(csv_file_path, limit)
    if not records:
        logger.error("No records to process")
        return {"updated": 0, "not_found": 0, "failed": 0}
    
    # Create filename to metadata mapping
    filename_to_metadata = {}
    for record in records:
        filename_to_metadata[record['ecopyfile']] = {
            'product_name': record['product_name'],
            'url': record['url']
        }
    
    # Initialize ChromaDB client
    db = chromadb.PersistentClient(path=persist_dir)
    
    try:
        # Get the collection
        collection = db.get_collection(name=collection_name)
        logger.info(f"Successfully accessed collection '{collection_name}'")
        
        # Get all documents
        results = collection.get(include=['metadatas', 'documents'])
        
        if not results or not results.get('ids'):
            logger.warning(f"No documents found in collection '{collection_name}'")
            return {"updated": 0, "not_found": 0, "failed": 0}
        
        ids = results['ids']
        metadatas = results['metadatas']
        documents = results['documents']
        
        stats = {"updated": 0, "not_found": 0, "failed": 0}
        
        # Update metadata for matching documents
        for i, metadata in enumerate(metadatas):
            if metadata and 'file_name' in metadata:
                filename = metadata['file_name']
                
                if filename in filename_to_metadata:
                    # Update metadata with product name and URL
                    csv_data = filename_to_metadata[filename]
                    
                    updated = False
                    if csv_data['product_name'] and csv_data['product_name'] != metadata.get('product_name'):
                        metadata['product_name'] = csv_data['product_name']
                        updated = True
                    
                    if csv_data['url'] and csv_data['url'] != metadata.get('document_url'):
                        metadata['document_url'] = csv_data['url']
                        updated = True
                    
                    if updated:
                        stats["updated"] += 1
                        logger.info(f"Updated metadata for {filename}: {csv_data['product_name']}")
                    else:
                        logger.debug(f"No changes needed for {filename}")
        
        if stats["updated"] > 0:
            # Update the collection with new metadata
            collection.update(
                ids=ids,
                metadatas=metadatas
            )
            logger.info(f"Successfully updated {stats['updated']} documents in ChromaDB")
        
        # Check for files in CSV that weren't found in ChromaDB
        processed_files = set()
        for metadata in metadatas:
            if metadata and 'file_name' in metadata:
                processed_files.add(metadata['file_name'])
        
        csv_files = set(filename_to_metadata.keys())
        not_found_files = csv_files - processed_files
        stats["not_found"] = len(not_found_files)
        
        if not_found_files:
            logger.warning(f"Files in CSV not found in ChromaDB: {not_found_files}")
        
        return stats
        
    except Exception as e:
        logger.error(f"Error updating document metadata: {e}", exc_info=True)
        return {"updated": 0, "not_found": 0, "failed": 1}

def main():
    parser = argparse.ArgumentParser(description='Update document metadata from CSV')
    parser.add_argument(
        '--limit',
        type=int,
        help='Maximum number of rows to process (default: process all)'
    )
    parser.add_argument(
        '--csv-file',
        type=str,
        default='cii-urls.csv',
        help='Path to CSV file (default: cii-urls.csv)'
    )
    parser.add_argument(
        '--collection',
        type=str,
        help='ChromaDB collection name (default: from config)'
    )
    
    args = parser.parse_args()
    
    # Check if CSV file exists
    if not os.path.exists(args.csv_file):
        logger.error(f"CSV file not found: {args.csv_file}")
        return
    
    # Run metadata update
    stats = update_document_metadata_from_csv(
        csv_file_path=args.csv_file,
        limit=args.limit,
        collection_name=args.collection
    )
    
    logger.info(f"Metadata update complete!")
    logger.info(f"✅ Updated: {stats['updated']}")
    logger.info(f"❌ Not found: {stats['not_found']}")
    logger.info(f"💥 Failed: {stats['failed']}")
    
    # Exit with appropriate code
    if stats["failed"] > 0:
        exit(1)
    else:
        exit(0)

if __name__ == "__main__":
    main()