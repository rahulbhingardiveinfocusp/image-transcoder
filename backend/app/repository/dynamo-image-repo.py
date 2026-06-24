from typing import Optional, List, Dict, Any
from boto3.dynamodb.conditions import Key
from app.services.dynamo_service import DynamoService



class DynamoImageRepository:
    def __init__(self, dynamo: DynamoService):
        self.dynamo = dynamo

    # -----------------------
    # CREATE IMAGE
    # -----------------------
    async def create(self, data: Dict[str, Any]) -> None:
        item = {
            "PK": f"IMAGE#{data['id']}",
            "SK": "METADATA",

            "id": data["id"],
            "filename": data["filename"],
            "status": data.get("status", "PENDING"),

            "s3_key": data["s3_key"],
            "s3_processed_file": data.get("s3_processed_file"),

            "created_at": data["created_at"],

            # GSI for status queries
            "GSI1PK": f"STATUS#{data.get('status', 'PENDING')}",
            "GSI1SK": data["created_at"],
        }

        await self.dynamo.put_item(item)

    # -----------------------
    # GET BY ID
    # -----------------------
    async def get_by_id(self, image_id: str) -> Optional[Dict[str, Any]]:
        return await self.dynamo.get_item(
            pk=f"IMAGE#{image_id}",
            sk="METADATA"
        )

    # -----------------------
    # UPDATE STATUS
    # -----------------------
    async def update_status(self, image_id: str, status: str) -> None:
        # NOTE: You MUST also update GSI fields to keep queries correct
        await self.dynamo.update_item(
            pk=f"IMAGE#{image_id}",
            sk="METADATA",
            update_expression="""
                SET #s = :status,
                    GSI1PK = :gsi_pk
            """,
            expression_names={
                "#s": "status"
            },
            expression_values={
                ":status": status,
                ":gsi_pk": f"STATUS#{status}"
            }
        )

    # -----------------------
    # LIST BY STATUS
    # -----------------------
    async def list_by_status(self, status: str) -> Dict[str, Any]:
        resp = await self.dynamo.query_by_gsi(
            index_name="GSI1",
            key_condition_expression=Key("GSI1PK").eq(f"STATUS#{status}"),
            expression_values={}
        )

        return {
            "items": resp.get("Items", []),
            "last_key": resp.get("LastEvaluatedKey")
        }

    # -----------------------
    # OPTIONAL: LIST RECENT
    # -----------------------
    async def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        # If you later add a "RECENT" GSI, this becomes efficient
        resp = await self.dynamo.table.scan(Limit=limit)
        return resp.get("Items", [])