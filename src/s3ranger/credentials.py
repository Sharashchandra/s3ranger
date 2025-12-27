from dataclasses import dataclass


@dataclass
class ResolvedCredentials:
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    profile_name: str | None = None

    source: str = ""

    def validate(self):
        if self.aws_access_key_id and not self.aws_secret_access_key:
            raise ValueError("aws_secret_access_key is required when aws_access_key_id is provided")
        if self.aws_secret_access_key and not self.aws_access_key_id:
            raise ValueError("aws_access_key_id is required when aws_secret_access_key is provided")

        if not any([self.aws_access_key_id, self.aws_secret_access_key, self.profile_name]):
            raise ValueError(
                "Credentials required: provide either a profile_name, or both aws_access_key_id and aws_secret_access_key. These can be specified via CLI arguments or by setting a profile name in the config file."
            )


class CredentialResolver:
    def resolve(self, context: dict) -> ResolvedCredentials | None: ...


class CLIAccessKeySecretKeyResolver(CredentialResolver):
    """Resolves credentials from CLI-provided access key and secret key."""

    def resolve(self, context: dict) -> ResolvedCredentials | None:
        access_key = context.get("cli_access_key")
        secret_key = context.get("cli_secret_key")
        session_token = context.get("cli_session_token")

        if access_key and secret_key:
            return ResolvedCredentials(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                aws_session_token=session_token,
                source="cli",
            )
        return


class CLIProfileResolver(CredentialResolver):
    """Resolves credentials from CLI-provided profile name."""

    def resolve(self, context: dict) -> ResolvedCredentials | None:
        profile_name = context.get("cli_profile")
        if profile_name:
            return ResolvedCredentials(
                profile_name=profile_name,
                source="cli",
            )
        return


class ConfigFileProfileResolver(CredentialResolver):
    """Resolves credentials from config file profile name."""

    def resolve(self, context: dict) -> ResolvedCredentials | None:
        config_profile_name = context.get("config_profile")
        if config_profile_name:
            return ResolvedCredentials(
                profile_name=config_profile_name,
                source="config_file",
            )
        return


class CredentialChain:
    """Chain of credential resolvers, returns first successful resolution."""

    def __init__(self, resolvers: list[CredentialResolver]):
        self.resolvers = resolvers

    def resolve(self, context: dict) -> ResolvedCredentials:
        for resolver in self.resolvers:
            result = resolver.resolve(context)
            if result:
                return result

        return ResolvedCredentials(source="default")


def resolve_credentials(
    cli_access_key: str | None,
    cli_secret_key: str | None,
    cli_session_token: str | None,
    cli_profile: str | None,
    config_profile: str | None,
) -> ResolvedCredentials:
    """
    Resolve credentials following strict priority order:
    1. CLI access key + secret key (highest priority)
    2. CLI profile name
    3. Config file profile name
    4. Error if nothing provided
    """
    context = {
        "cli_access_key": cli_access_key,
        "cli_secret_key": cli_secret_key,
        "cli_session_token": cli_session_token,
        "cli_profile": cli_profile,
        "config_profile": config_profile,
    }

    chain = CredentialChain(
        [
            CLIAccessKeySecretKeyResolver(),
            CLIProfileResolver(),
            ConfigFileProfileResolver(),
        ]
    )

    return chain.resolve(context)
