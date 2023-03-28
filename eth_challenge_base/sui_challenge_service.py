import os
import pyseto

from decimal import Decimal
from glob import glob
from typing import Dict
from pyseto import Token
from eth_challenge_base.config import Config, parse_config
from twirp import ctxkeys, errors
from twirp.asgi import TwirpASGIApp
from twirp.exceptions import RequiredArgument, TwirpServerException
from eth_challenge_base.sui_config import SuiConfig
from eth_challenge_base.sui import SuiAccount, SuiContract, SuiClient
from eth_challenge_base.protobuf import sui_challenge_pb2, sui_challenge_twirp

AUTHORIZATION_KEY = "authorization"

unit = Decimal("1000000000")


class SuiChallengeService:
    def __init__(self, project_root: str, config: Config) -> None:
        self._config = config
        if not self._config.solved_event:
            raise TwirpServerException(
                code=errors.Errors.FailedPrecondition,
                message=f"To solve the SUI challenge, the 'solve_event' parameter is required and cannot be left empty.",
            )
        self._project_root = project_root
        artifact_path = os.path.join(self._project_root, "sources")
        self._contract: SuiContract = SuiContract(
            self._config.contract,
            self._config.module,
        )
        self._source_code: Dict[str, str] = self._load_challenge_sui_source(
            artifact_path
        )
        self._token_key = pyseto.Key.new(
            version=4,
            purpose="local",
            key=os.getenv("TOKEN_KEY"),
        )

    def GetChallengeInfo(self, context, empty):
        return sui_challenge_pb2.Info(
            description=self._config.description,
            show_source=self._config.show_source,
            solved_event=self._config.solved_event,
        )

    def NewPlayground(self, context, empty):
        client = self.new_client()
        account: SuiAccount = SuiAccount(client)
        token: str = pyseto.encode(
            self._token_key, payload=account.key_store, footer=self._config.contract
        ).decode("utf-8")

        try:
            constructor = self._config.constructor
            total_value: int = constructor.value
        except Exception as e:
            raise TwirpServerException(
                code=errors.Errors.Internal,
                message=str(e),
            )

        sui_value: Decimal = Decimal(total_value) / unit + Decimal("0.001")

        context.get_logger().info("Playground account %s was created", account.address)
        context.get_logger().info(f"address list is: {client.config.addresses}")
        return sui_challenge_pb2.Playground(
            address=account.address,
            token=token,
            value=float(round(sui_value, 3)),
        )

    def DeployContract(self, context, empty):
        client = self.new_client()
        account: SuiAccount = self._recoverAcctFromCtx(context)
        if account.balance(client) == 0:
            raise TwirpServerException(
                code=errors.Errors.FailedPrecondition,
                message=f"send test sui to {account.address} first",
            )

        contract_addr: str = account.get_deployment_address(client)
        if contract_addr != "":
            raise TwirpServerException(
                code=errors.Errors.FailedPrecondition,
                message=f"contract {contract_addr} has already deployed",
            )
        try:
            contract_path = os.path.join(self._project_root, "contracts")
            context.get_logger().info(
                f"deployment address list is: {client.config.addresses}"
            )
            tx_hash, contract_addr = self._contract.publish(
                client,
                account,
                contract_path,
            )
        except Exception as e:
            raise TwirpServerException(
                code=errors.Errors.Internal,
                message=str(e),
            )

        context.get_logger().info(
            "Contract %s was deployed by %s. Transaction hash %s",
            contract_addr,
            account.address,
            tx_hash,
        )
        return sui_challenge_pb2.Contract(address=contract_addr, tx_hash=tx_hash)

    def GetFlag(self, context, event):
        client = self.new_client()
        account: SuiAccount = self._recoverAcctFromCtx(context)
        contract_addr: str = account.get_deployment_address(client)
        if contract_addr == "":
            raise TwirpServerException(
                code=errors.Errors.FailedPrecondition,
                message="challenge contract has not yet been deployed",
            )
        if not event.HasField("tx_hash"):
            raise RequiredArgument(argument="tx_hash")
        tx_hash = event.tx_hash.strip()
        try:
            is_solved = self._contract.is_solved(
                client,
                contract_addr,
                self._config.solved_event,
                tx_hash,
            )
        except Exception as e:
            raise TwirpServerException(
                code=errors.Errors.FailedPrecondition,
                message=str(e),
            )

        if not is_solved:
            raise TwirpServerException(
                code=errors.Errors.InvalidArgument,
                message="you haven't solved this challenge",
            )

        context.get_logger().info(
            "Flag was captured in contract %s deployed by %s",
            contract_addr,
            account.address,
        )

        flag: str = self._config.flag
        return sui_challenge_pb2.Flag(flag=flag)

    def GetSourceCode(self, context, token):
        return sui_challenge_pb2.SourceCode(source=self._source_code)

    def _load_challenge_sui_source(self, artifact_path) -> Dict[str, str]:
        source: Dict[str, str] = {}
        if not self._config.show_source:
            return source
        for path in glob(os.path.join(artifact_path, "*.move")):
            with open(path) as f:
                content = f.read()
                source[path] = content
        return source

    def _recoverAcctFromCtx(self, context) -> SuiAccount:
        header = context.get(ctxkeys.RAW_HEADERS)
        token = header.get(AUTHORIZATION_KEY)
        if not token:
            raise RequiredArgument(argument="authorization")

        try:
            decoded_token: Token = pyseto.decode(self._token_key, token.strip())
        except Exception as e:
            raise TwirpServerException(
                code=errors.Errors.Unauthenticated, message=str(e)
            )

        if self._config.contract != decoded_token.footer.decode("utf-8"):  # type: ignore[union-attr]
            raise TwirpServerException(
                code=errors.Errors.Unauthenticated,
                message="token was not issued by this challenge",
            )

        return SuiAccount(keystring=decoded_token.payload.decode("utf-8"))  # type: ignore[union-attr]

    def new_client(self):
        return SuiClient(
            SuiConfig(
                config_path=os.getenv("SUI_CLIENT_CONFIG"),
                env=os.getenv("SUI_ENV"),
                keystore_file=os.getenv("SUI_KEYSTORE_FILE"),
                current_url=os.getenv("SUI_PROVIDER_URL"),
            )
        )


def create_asgi_application(project_root: str) -> TwirpASGIApp:
    config = parse_config(os.path.join(project_root, "challenge.yml"))
    application = TwirpASGIApp()
    service = SuiChallengeService(project_root, config)
    application.add_service(sui_challenge_twirp.SuiChallengeServer(service=service))
    return application
