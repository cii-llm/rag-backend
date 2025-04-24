# app/node_processing.py
import logging
from llama_index.core.postprocessor.types import BaseNodePostprocessor
from llama_index.core.schema import NodeWithScore, QueryBundle
from typing import List, Optional

logger = logging.getLogger(__name__)

class MetadataCitationPostprocessor(BaseNodePostprocessor):
    """
    Appends source metadata (filename, page) to the node's text content
    before it's sent to the LLM for synthesis.
    """
    def _postprocess_nodes(
        self,
        nodes: List[NodeWithScore],
        query_bundle: Optional[QueryBundle] = None,
    ) -> List[NodeWithScore]:
        processed_nodes = []
        for node_with_score in nodes:
            node = node_with_score.node
            try:
                file_name = node.metadata.get("file_name", "Unknown Source")
                page_label = node.metadata.get("page_label", None) # PDFs often have this

                # Create the citation string
                citation = f"[Source: {file_name}"
                if page_label:
                    citation += f", Page: {page_label}"
                citation += "]"

                # Prepend citation to the node's text for the LLM context
                # Using a clear separator helps the LLM distinguish context from citation info
                modified_text = f"{citation}\n---\n{node.get_content()}"

                # Create a new node or modify the existing one (careful about side effects)
                # Creating a new node instance is safer
                new_node = node.copy()
                new_node.set_content(modified_text)

                processed_nodes.append(NodeWithScore(node=new_node, score=node_with_score.score))
                # logger.debug(f"Postprocessed node with text: {modified_text[:100]}...") # Log snippet if needed

            except Exception as e:
                logger.error(f"Error processing node metadata: {e}", exc_info=True)
                # Append the original node if processing fails
                processed_nodes.append(node_with_score)

        logger.info(f"MetadataCitationPostprocessor added citations to {len(processed_nodes)} nodes.")
        return processed_nodes