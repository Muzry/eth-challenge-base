import threading
import base64
from pathlib import Path
from pysui.sui.sui_utils import build_b64_modules
from pysui.abstracts import SignatureScheme
from pysui.sui.sui_clients.sync_client import SuiClient, SuiAddress, SuiMap

from pysui.sui.sui_crypto import (
    keypair_from_keystring,
    create_new_address,
)


class SuiAccount:
    def __init__(self, client: SuiClient = None, keystring: str = None) -> None:
        self._lock = threading.Lock()
        if keystring is None:
            mem, key_pair, sui_address = client.config.create_new_keypair_and_address(
                SignatureScheme.ED25519
            )

        else:
            key_pair = keypair_from_keystring(keystring)
            sui_address = SuiAddress.from_bytes(key_pair.to_bytes())
        self._account = sui_address
        self.address = self._account.address
        self.key_pair = key_pair
        key_store = b"\x00" + key_pair.private_key.key_bytes
        self.key_store = base64.standard_b64encode(key_store).decode("utf-8")

    def balance(self, client) -> int:
        client.config.set_active_address(self.address)
        result = client._get_coins_for_type(self.address)
        balance = 0
        for item in result.result_data.data:
            balance = balance + item.balance
        return balance

    def get_deployment_address(self, client: SuiClient):
        result = client.get_events(
            query=SuiMap("Sender", self.address),
            cursor=None,
            limit=None,
            descending_order=False,
        )
        for item in result.result_data.data:
            publish = item.event.get("publish", None)
            if publish and publish.sender == self.address:
                return publish.package_id
        return ""


class SuiContract:
    def __init__(self, contract_name: str, contract_module: str) -> None:
        self.contract_name = contract_name
        self.contract_module = contract_module

    def get_publish_args(self, address, project_root, client: SuiClient):
        result = client._get_coins_for_type(address)
        object_id = ""
        for item in result.result_data.data:
            object_id = item.coin_object_id
            break
        return {
            "sender": address,
            "compiled_modules": build_b64_modules(
                path_to_package=project_root, skip_git_dependencie=True
            ),
            "gas": object_id,
            "gas_budget": 3000,
        }

    def get_deployment_info(self, client: SuiClient):
        result = client.get_events(
            query=SuiMap("Sender", client.config.active_address),
            cursor=None,
            limit=None,
            descending_order=False,
        )
        for item in result.result_data.data:
            publish = item.event.get("publish", None)
            if publish and publish.sender == client.config.active_address:
                return item.transaction_digest, publish.package_id
        return "", ""

    def publish(self, client, account, project_root):
        var_args = self.get_publish_args(account.address, Path(project_root), client)
        client.publish_package_txn(**var_args)
        return self.get_deployment_info(client)

    def is_solved(
        self,
        client: SuiClient,
        address: str,
        solved_event: str = "",
        tx_hash: str = "",
    ) -> bool:
        is_solved = False
        if solved_event:
            result = client.get_events(
                query=SuiMap("Transaction", tx_hash),
                cursor=None,
                limit=None,
                descending_order=False,
            )
            event_type = f"{address}::{self.contract_module}::{solved_event}"
            for item in result.result_data.data:
                moveEvent = item.event.get("moveEvent", None)

                if (
                    moveEvent
                    and moveEvent.event_type == event_type
                    and moveEvent.package_id == address
                ):
                    is_solved = True
        return is_solved
