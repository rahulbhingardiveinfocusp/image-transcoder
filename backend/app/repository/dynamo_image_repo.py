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

            "id": str(data["id"]),
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
            sk="METADATA",
        )

    # -----------------------
    # UPDATE STATUS
    # -----------------------
    async def update_status(self, image_id: str, status: str, processed_key: Optional[str] = None) -> None:
        item = await self.dynamo.get_item(pk=f"IMAGE#{image_id}", sk="METADATA")
        gsi_sk = item["created_at"] if item else ""

        update_expr = "SET #s = :status, GSI1PK = :gsi_pk, GSI1SK = :gsi_sk"
        expression_values: Dict[str, Any] = {
            ":status": status,
            ":gsi_pk": f"STATUS#{status}",
            ":gsi_sk": gsi_sk,                    # FIX: was missing in original
        }

        if processed_key is not None:
            update_expr += ", s3_processed_file = :s3_processed_file"
            expression_values[":s3_processed_file"] = processed_key

        await self.dynamo.update_item(
            pk=f"IMAGE#{image_id}",
            sk="METADATA",
            update_expression=update_expr,
            expression_names={"#s": "status"},
            expression_values=expression_values,
        )

    # -----------------------
    # LIST BY STATUS
    # -----------------------
    async def list_by_status(self, status: str) -> Dict[str, Any]:
        resp = await self.dynamo.query_by_gsi(
            index_name="GSI1",
            key_condition_expression=Key("GSI1PK").eq(f"STATUS#{status}"),
        )
        return {
            "items": resp.get("Items", []),
            "last_key": resp.get("LastEvaluatedKey"),
        }

    # -----------------------
    # LIST ALL (scan — dev/small tables only)
    # -----------------------
    async def list_all(self) -> List[Dict[str, Any]]:
        import anyio
        resp = await anyio.to_thread.run_sync(
            lambda: self.dynamo.table.scan(
                FilterExpression="SK = :sk",
                ExpressionAttributeValues={":sk": "METADATA"},
            )
        )
        items = resp.get("Items", [])
        # sort descending by created_at (mirrors the old ORDER BY created_at DESC)
        items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return items