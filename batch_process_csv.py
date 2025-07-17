#!/usr/bin/env python3
"""
CSV Batch Processing Script for CII Documents

This script processes documents from a CSV file containing Product Name, eCopyfile, and CII Website URL.
It copies files from the cii-pdfs/ folder to the data/ folder and processes them into ChromaDB.

Usage:
    python batch_process_csv.py [--limit N] [--csv-file path/to/csv]
    
Example:
    python batch_process_csv.py --limit 2  # Process first 2 rows
    python batch_process_csv.py  # Process all rows
"""

import os
import csv
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional
import argparse

# Import the preprocessing module
from app import preprocessing, config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def read_csv_file(csv_file_path: str, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """
    Read the CSV file and return a list of document records.
    
    Args:
        csv_file_path: Path to the CSV file
        limit: Maximum number of rows to process (None for all)
        
    Returns:
        List of dictionaries with keys: product_name, ecopyfile, url
    """
    records = []
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8-sig') as file:
            reader = csv.DictReader(file)
            
            for i, row in enumerate(reader):
                if limit and i >= limit:
                    break
                    
                # Clean and validate the row data
                record = {
                    'product_name': row.get('Product Name', '').strip(),
                    'ecopyfile': row.get('eCopyfile', '').strip(),
                    'url': row.get('CII Website URL', '').strip()
                }
                
                # Skip empty rows
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

def copy_file_to_data_folder(source_file: str, data_folder: str) -> bool:
    """
    Copy a file from the cii-pdfs folder to the data folder.
    
    Args:
        source_file: Name of the file to copy
        data_folder: Destination folder path
        
    Returns:
        True if successful, False otherwise
    """
    source_path = Path("cii-pdfs") / source_file
    dest_path = Path(data_folder) / source_file
    
    try:
        # Create data folder if it doesn't exist
        os.makedirs(data_folder, exist_ok=True)
        
        # Check if source file exists
        if not source_path.exists():
            logger.error(f"Source file not found: {source_path}")
            return False
        
        # Copy the file
        shutil.copy2(source_path, dest_path)
        logger.info(f"Copied {source_file} to {data_folder}")
        return True
        
    except Exception as e:
        logger.error(f"Error copying file {source_file}: {e}")
        return False

def process_csv_batch(
    csv_file_path: str = "cii-urls.csv",
    limit: Optional[int] = None,
    collection_name: str = None,
    data_folder: str = None,
    persist_dir: str = None
) -> Dict[str, int]:
    """
    Process documents from CSV file in batch.
    
    Args:
        csv_file_path: Path to the CSV file
        limit: Maximum number of rows to process
        collection_name: ChromaDB collection name
        data_folder: Folder to store documents
        persist_dir: ChromaDB persistence directory
        
    Returns:
        Dictionary with processing statistics
    """
    # Use config defaults if not provided
    collection_name = collection_name or config.COLLECTION_NAME
    data_folder = data_folder or str(config.DATA_FOLDER)
    persist_dir = persist_dir or str(config.PERSIST_DIR)
    
    logger.info(f"Starting CSV batch processing")
    logger.info(f"CSV file: {csv_file_path}")
    logger.info(f"Data folder: {data_folder}")
    logger.info(f"Collection: {collection_name}")
    logger.info(f"Limit: {limit or 'No limit'}")
    
    # Read CSV records
    records = read_csv_file(csv_file_path, limit)
    if not records:
        logger.error("No records to process")
        return {"processed": 0, "failed": 0, "skipped": 0}
    
    stats = {"processed": 0, "failed": 0, "skipped": 0}
    
    for i, record in enumerate(records, 1):
        logger.info(f"Processing record {i}/{len(records)}: {record['ecopyfile']}")
        
        try:
            # Copy file to data folder
            if not copy_file_to_data_folder(record['ecopyfile'], data_folder):
                stats["failed"] += 1
                continue
            
            # Process the document
            file_path = Path(data_folder) / record['ecopyfile']
            
            # Call preprocessing with the specific file
            num_processed = preprocessing.process_and_store_documents(
                data_folder=str(file_path.parent),
                collection_name=collection_name,
                persist_dir=persist_dir,
                document_url=record['url'],
                product_name=record['product_name']
            )
            
            if num_processed > 0:
                stats["processed"] += 1
                logger.info(f"✅ Successfully processed: {record['ecopyfile']} ({record['product_name']})")
            else:
                stats["skipped"] += 1
                logger.info(f"⏭️  Skipped (already processed): {record['ecopyfile']}")
                
        except Exception as e:
            logger.error(f"❌ Failed to process {record['ecopyfile']}: {e}")
            stats["failed"] += 1
    
    logger.info(f"Batch processing complete!")
    logger.info(f"✅ Processed: {stats['processed']}")
    logger.info(f"⏭️  Skipped: {stats['skipped']}")
    logger.info(f"❌ Failed: {stats['failed']}")
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Batch process CII documents from CSV')
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
    
    # Check if cii-pdfs folder exists
    if not os.path.exists('cii-pdfs'):
        logger.error("cii-pdfs folder not found. Please create it and add your PDF files.")
        return
    
    # Run batch processing
    stats = process_csv_batch(
        csv_file_path=args.csv_file,
        limit=args.limit,
        collection_name=args.collection
    )
    
    # Exit with appropriate code
    if stats["failed"] > 0:
        exit(1)
    else:
        exit(0)

if __name__ == "__main__":
    main()