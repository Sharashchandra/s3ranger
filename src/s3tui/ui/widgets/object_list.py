"""Object list widget for displaying S3 bucket objects."""

from textual.message import Message
from textual.widgets import Tree

from s3tui.gateways.s3 import S3


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

    def __init__(self, **kwargs):
        super().__init__("Root", **kwargs)
        self.objects = []
        self.current_bucket = None
        self._loading = False
        self._object_nodes = {}  # Maps object keys to tree nodes
        self._folder_paths = {}  # Maps nodes to their folder paths

    def show_loading(self, bucket_name: str) -> None:
        """Show loading state for the object list."""
        self.clear()
        self._loading = True
        self.current_bucket = bucket_name
        self._object_nodes.clear()
        self._folder_paths.clear()
        self.root.add_leaf(f"Loading objects from {bucket_name}...")

    def show_empty_bucket(self, bucket_name: str) -> None:
        """Show empty bucket state."""
        self.clear()
        self._loading = False
        self.current_bucket = bucket_name
        self._object_nodes.clear()
        self._folder_paths.clear()
        self.root.add_leaf(f"Bucket '{bucket_name}' is empty")

    def show_placeholder(self) -> None:
        """Show placeholder when no bucket is selected."""
        self.clear()
        self._loading = False
        self.current_bucket = None
        self._object_nodes.clear()
        self._folder_paths.clear()
        self.root.add_leaf("Select a bucket to view its contents")

    def _build_tree_structure(self, objects):
        """Build a hierarchical tree structure from flat object list."""
        # Clear existing tree
        self.clear()
        self._object_nodes.clear()
        self._folder_paths.clear()

        # Dictionary to track folder nodes
        folder_nodes = {}

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
                    if size > 0:
                        # Format size in human-readable format
                        if size < 1024:
                            size_str = f"{size} B"
                        elif size < 1024 * 1024:
                            size_str = f"{size / 1024:.1f} KB"
                        elif size < 1024 * 1024 * 1024:
                            size_str = f"{size / (1024 * 1024):.1f} MB"
                        else:
                            size_str = f"{size / (1024 * 1024 * 1024):.1f} GB"
                    else:
                        size_str = "0 B"

                    # Add file node with size
                    display_text = f"{part} ({size_str})"
                    file_node = current_node.add_leaf(display_text)
                    # Store the full object key for this node
                    file_node.data = object_key
                    self._object_nodes[object_key] = file_node
                else:
                    # This is a folder
                    if current_path:
                        current_path += f"/{part}"
                    else:
                        current_path = part

                    # Check if we already have this folder node
                    if current_path not in folder_nodes:
                        folder_node = current_node.add(f"📁 {part}")
                        folder_node.data = None  # Folders don't have object data
                        folder_nodes[current_path] = folder_node
                        # Track the folder path for this node
                        self._folder_paths[folder_node] = current_path

                    current_node = folder_nodes[current_path]

    async def load_objects_for_bucket(self, bucket_name: str, prefix: str = None) -> None:
        """Load objects for the specified bucket."""
        self.show_loading(bucket_name)

        try:
            # Fetch objects in background thread
            objects = S3.list_objects(bucket_name=bucket_name, prefix=prefix)

            # Update UI on main thread
            self.objects = objects
            self.current_bucket = bucket_name
            self._loading = False

            if not objects:
                self.show_empty_bucket(bucket_name)
                return

            # Build the tree structure
            self._build_tree_structure(objects)

        except Exception as e:
            # Show error and keep focusable
            self.clear()
            self._loading = False
            self.current_bucket = bucket_name
            self.root.add_leaf(f"Error loading objects: {str(e)}")

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if self._loading:
            return

        node = event.node
        # Check if this node represents a file (has object data)
        if hasattr(node, "data") and node.data is not None:
            object_key = node.data
            if self.current_bucket:
                # Post a message to the parent screen with the actual object key
                self.post_message(self.ObjectSelected(object_key, self.current_bucket))
        # Check if this node represents a folder
        elif node in self._folder_paths:
            folder_path = self._folder_paths[node]
            if self.current_bucket:
                # Post a message with folder path (add trailing slash to indicate it's a folder)
                folder_key = f"{folder_path}/"
                self.post_message(self.ObjectSelected(folder_key, self.current_bucket))

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        """Handle tree node expansion - update path bar when folder is opened."""
        if self._loading or not self.current_bucket:
            return

        node = event.node
        # Check if this is a folder node (has folder path but no object data)
        if node in self._folder_paths:
            folder_path = self._folder_paths[node]
            self.post_message(self.FolderNavigated(folder_path, self.current_bucket))

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        """Handle tree node collapse - update path bar when folder is closed."""
        if self._loading or not self.current_bucket:
            return

        node = event.node
        # When a folder is collapsed, navigate to its parent folder
        if node in self._folder_paths:
            folder_path = self._folder_paths[node]
            # Get parent folder path
            if "/" in folder_path:
                parent_path = "/".join(folder_path.split("/")[:-1])
            else:
                # If no parent, navigate back to bucket root
                parent_path = ""
            self.post_message(self.FolderNavigated(parent_path, self.current_bucket))

    def refresh_objects(self) -> None:
        """Refresh the object list for the current bucket."""
        if self.current_bucket:
            self.run_worker(self.load_objects_for_bucket(self.current_bucket))
        else:
            self.show_placeholder()
