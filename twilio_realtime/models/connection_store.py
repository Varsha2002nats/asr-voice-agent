"""
ConnectionStore class for managing websocket connections.
"""


class ConnectionStore:
    """
    Global object to store websocket connection info.
    """

    def __init__(self):
        """Initialize an empty connection store."""
        self.connections = {}

    def add_connection(self, websocket_id, data):
        """
        Add or update a connection's data.

        Args:
            websocket_id: The unique identifier for the connection
            data: The data to store for this connection
        """
        # Initialize messages list if it doesn't exist
        if "messages" not in data:
            data["messages"] = []
        self.connections[websocket_id] = data

    def get_connection(self, websocket_id):
        """
        Get a connection's data.

        Args:
            websocket_id: The unique identifier for the connection

        Returns:
            The connection data or None if not found
        """
        return self.connections.get(websocket_id)

    def add_message(self, websocket_id, role, message, timestamp=None):
        """
        Add a message to the connection's message history.

        Args:
            websocket_id: The unique identifier for the connection
            role: The role of the message sender ("user" or "assistant")
            message: The content of the message
            timestamp: Optional timestamp for the message
        """
        connection = self.get_connection(websocket_id)
        if connection:
            if "messages" not in connection:
                connection["messages"] = []

            connection["messages"].append(
                {"role": role, "content": message, "timestamp": timestamp}
            )

    def get_messages(self, websocket_id):
        """
        Get all messages for a connection.

        Args:
            websocket_id: The unique identifier for the connection

        Returns:
            List of messages or empty list if none found
        """
        connection = self.get_connection(websocket_id)
        if connection and "messages" in connection:
            return connection["messages"]
        return []

    def remove_connection(self, websocket_id):
        """
        Remove a connection.

        Args:
            websocket_id: The unique identifier for the connection to remove
        """
        if websocket_id in self.connections:
            del self.connections[websocket_id]

    def __str__(self):
        return f"ConnectionStore with {len(self.connections)} active connections"


# Create a global instance
connections = ConnectionStore()
