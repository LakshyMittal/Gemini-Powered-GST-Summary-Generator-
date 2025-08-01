# gst_details.py

from database.database_config import NetworkConnections


class GSTDetailsDatabase:
    def __init__(self, connection: NetworkConnections):
        self.db = connection.get_mongo_db()
        self.collection = self.db["gstDetails"]

    async def get_gst_details_by_number(self, gst_number: str):
        return self.collection.find_one({"gstNumber": gst_number})
