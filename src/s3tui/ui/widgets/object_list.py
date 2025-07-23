"""Object list widget for displaying S3 bucket objects."""

from textual.message import Message
from textual.widgets import Tree

from s3tui.gateways.s3 import S3
from s3tui.ui.utils import (
    format_folder_display_text,
    format_object_display_text,
    get_parent_path,
)

# Constants for better maintainability
EMPTY_BUCKET_MESSAGE = "Bucket is empty"
PLACEHOLDER_MESSAGE = "Select a bucket to view its contents"
ERROR_PREFIX = "Error loading objects: "


class ObjectList(Tree):
    """Widget for displaying and selecting S3 bucket objects in a tree structure."""

    class ObjectSelected(Message):
        """Message sent when an object is selected."""

        def __init__(self, object_key: str, bucket_name: str) -> None:
            self.object_key = object_key
            self.bucket_name = bucket_name
            super().__init__()

    class FolderNavigated(Message):
        """Message sent when navigating to a folder."""

        def __init__(self, folder_path: str, bucket_name: str) -> None:
            self.folder_path = folder_path
            self.bucket_name = bucket_name
            super().__init__()

    def __init__(self, **kwargs) -> None:
        super().__init__("Root", **kwargs)
        self.objects: list[dict] = []
        self.current_bucket: str | None = None
        self._object_nodes: dict[str, Tree] = {}  # Maps object keys to tree nodes
        self._folder_paths: dict[Tree, str] = {}  # Maps nodes to their folder paths

    def _clear_state(self) -> None:
        """Clear internal state and tree structure."""
        self.clear()
        self._object_nodes.clear()
        self._folder_paths.clear()

    def show_empty_bucket(self, bucket_name: str) -> None:
        """Show empty bucket state."""
        self._clear_state()
        self.current_bucket = bucket_name
        self.root.add_leaf(f"{EMPTY_BUCKET_MESSAGE}")

    def show_placeholder(self) -> None:
        """Show placeholder when no bucket is selected."""
        self._clear_state()
        self.current_bucket = None
        self.root.add_leaf(PLACEHOLDER_MESSAGE)

    def _show_error(self, error_message: str, bucket_name: str) -> None:
        """Display an error message in the tree."""
        self._clear_state()
        self.current_bucket = bucket_name
        self.root.add_leaf(f"{ERROR_PREFIX}{error_message}")

    def _create_file_node(self, parent_node: Tree, name: str, object_key: str, size: int) -> None:
        """Create a file node in the tree.

        Args:
            parent_node: Parent tree node
            name: File name to display
            object_key: Full S3 object key
            size: File size in bytes
        """
        display_text = format_object_display_text(name, size)
        file_node = parent_node.add_leaf(display_text)
        file_node.data = object_key
        self._object_nodes[object_key] = file_node

    def _create_folder_node(self, parent_node: Tree, name: str, folder_path: str) -> Tree:
        """Create a folder node in the tree.

        Args:
            parent_node: Parent tree node
            name: Folder name to display
            folder_path: Full folder path

        Returns:
            Created folder node
        """
        display_text = format_folder_display_text(name)
        folder_node = parent_node.add(display_text)
        folder_node.data = None  # Folders don't have object data
        self._folder_paths[folder_node] = folder_path
        return folder_node

    def _build_tree_structure(self, objects: list[dict]) -> None:
        """Build a hierarchical tree structure from flat object list.

        Args:
            objects: List of S3 object dictionaries
        """
        self._clear_state()

        # Dictionary to track folder nodes by their full path
        folder_nodes: dict[str, Tree] = {}

        # Sort objects to ensure consistent display order
        sorted_objects = sorted(objects, key=lambda x: x["Key"])

        for obj in sorted_objects:
            object_key = obj["Key"]
            size = obj.get("Size", 0)
            parts = object_key.split("/")

            # Track current node position in tree
            current_node = self.root
            current_path = ""

            # Process each part of the path
            for i, part in enumerate(parts):
                if i == len(parts) - 1:
                    # This is the final file
                    self._create_file_node(current_node, part, object_key, size)
                else:
                    # This is a folder
                    current_path = f"{current_path}/{part}" if current_path else part

                    # Check if we already have this folder node
                    if current_path not in folder_nodes:
                        folder_node = self._create_folder_node(current_node, part, current_path)
                        folder_nodes[current_path] = folder_node

                    current_node = folder_nodes[current_path]

    async def load_objects_for_bucket(self, bucket_name: str, prefix: str = None) -> None:
        """Load objects for the specified bucket.

        Args:
            bucket_name: Name of the S3 bucket
            prefix: Optional prefix to filter objects
        """
        try:
            # Fetch objects from S3
            objects = S3.list_objects(bucket_name=bucket_name, prefix=prefix)

            # Update state
            self.objects = objects
            self.current_bucket = bucket_name

            if not objects:
                self.show_empty_bucket(bucket_name)
                return

            # Build the tree structure
            self._build_tree_structure(objects)

        except Exception as e:
            self._show_error(str(e), bucket_name)

    def _is_file_node(self, node: Tree) -> bool:
        """Check if a node represents a file (has object data).

        Args:
            node: Tree node to check

        Returns:
            True if node represents a file
        """
        return hasattr(node, "data") and node.data is not None

    def _is_folder_node(self, node: Tree) -> bool:
        """Check if a node represents a folder.

        Args:
            node: Tree node to check

        Returns:
            True if node represents a folder
        """
        return node in self._folder_paths

    def _is_root_node(self, node: Tree) -> bool:
        """Check if a node is the root node.

        Args:
            node: Tree node to check

        Returns:
            True if node is the root node
        """
        return node == self.root

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if not self.current_bucket:
            return

        node = event.node

        # Check if this node represents a file (has object data)
        if self._is_file_node(node):
            object_key = node.data
            self.post_message(self.ObjectSelected(object_key, self.current_bucket))
        # Check if this node represents a folder
        elif self._is_folder_node(node):
            folder_path = self._folder_paths[node]
            # Post a message with folder path (add trailing slash to indicate it's a folder)
            folder_key = f"{folder_path}/"
            self.post_message(self.ObjectSelected(folder_key, self.current_bucket))

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle tree node expansion - update path bar when folder is opened."""
        if not self.current_bucket:
            return

        node = event.node

        # Check if this is a folder node (has folder path but no object data)
        if self._is_folder_node(node):
            folder_path = self._folder_paths[node]
            self.post_message(self.FolderNavigated(folder_path, self.current_bucket))

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        """Handle tree node collapse - update path bar when folder is closed."""
        if not self.current_bucket:
            return

        node = event.node

        # Handle root node collapse - reset to bucket name
        if self._is_root_node(node):
            self.post_message(self.FolderNavigated("", self.current_bucket))
            return

        # When a folder is collapsed, navigate to its parent folder
        if self._is_folder_node(node):
            folder_path = self._folder_paths[node]
            parent_path = get_parent_path(folder_path)
            self.post_message(self.FolderNavigated(parent_path, self.current_bucket))

    def refresh_objects(self) -> None:
        """Refresh the object list for the current bucket."""
        if self.current_bucket:
            self.run_worker(self.load_objects_for_bucket(self.current_bucket))
        else:
            self.show_placeholder()
