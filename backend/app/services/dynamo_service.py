from app.core.config import Settings
import boto3
import anyio
from typing import Optional, Dict, Any, List
from typing import Optional, Any, List

def format_response(items: List[dict], last_key: Optional[dict]):
    return {
        "items": items,
        "last_evaluated_key": last_key
    }
class DynamoService:

    def __init__(self, table_name: str, ):
        self.dynamodb = boto3.resource("dynamodb", region_name=Settings.AWS_REGION)
        self.table = self.dynamodb.Table(table_name)

    # -----------------------
    # INTERNAL SYNC METHODS
    # -----------------------

    def _get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        resp = self.table.get_item(
            Key={
                "PK": pk,
                "SK": sk
            }
        )
        return resp.get("Item")

    def _put_item(self, item: Dict[str, Any]) -> None:
        self.table.put_item(Item=item)

    def _delete_item(self, pk: str, sk: str) -> None:
        self.table.delete_item( Key={
                "PK": pk,
                "SK": sk
            })

    def _update_item(
        self,
        pk: str,
        sk: str,
        update_expression: str,
        expression_values: Dict[str, Any],
        expression_names: Optional[Dict[str, str]] = None,
    ):
        params = {
            "Key": {"PK": pk, "SK": sk},
            "UpdateExpression": update_expression,
            "ExpressionAttributeValues": expression_values,
        }

        if expression_names:
            params["ExpressionAttributeNames"] = expression_names

        return self.table.update_item(**params)
    
    def _query_by_gsi(
        self,
        index_name: str,
        key_condition_expression,
        expression_values: Dict[str, Any],
        limit: int = 20,
        scan_forward: bool = False,
        exclusive_start_key: Optional[Dict[str, Any]] = None,
        expression_names: Optional[Dict[str, str]] = None,
    ):
        params = {
            "IndexName": index_name,
            "KeyConditionExpression": key_condition_expression,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit,
            "ScanIndexForward": scan_forward,
        }

        if exclusive_start_key:
            params["ExclusiveStartKey"] = exclusive_start_key

        if expression_names:
            params["ExpressionAttributeNames"] = expression_names

        return self.table.query(**params)

    
    # -----------------------
    # ASYNC PUBLIC METHODS
    # -----------------------

    async def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        return await anyio.to_thread.run_sync(
            self._get_item, pk, sk
        )

    async def put_item(self, item: Dict[str, Any]) -> None:
        return await anyio.to_thread.run_sync(
            self._put_item, item
        )
    async def delete_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        return await anyio.to_thread.run_sync(
            self._delete_item, pk, sk
        )
    
    async def update_item(
        self,
        pk: str,
        sk: str,
        update_expression: str,
        expression_values: Dict[str, Any],
        expression_names: Optional[Dict[str, str]] = None,
    ):
        return await anyio.to_thread.run_sync(
            self._update_item,
            pk,
            sk,
            update_expression,
            expression_values,
            expression_names,
        )
    async def query_by_gsi(
        self,
        index_name: str,
        key_condition_expression,
        expression_values: Dict[str, Any],
        expression_names: Optional[Dict[str, str]] = None,
    ):
        return await anyio.to_thread.run_sync(
            self._query_by_gsi,
            index_name,
            key_condition_expression,
            expression_values,
            expression_names,
        )