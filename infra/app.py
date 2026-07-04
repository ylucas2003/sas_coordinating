#!/usr/bin/env python3
import os

import aws_cdk as cdk
from dotenv import load_dotenv

from sas_scheduler.sas_scheduler_stack import SasSchedulerStack

load_dotenv()  # lê infra/.env se existir — não sobrescreve env vars já exportadas no shell

app = cdk.App()

api_base_url = app.node.try_get_context("apiBaseUrl") or os.environ.get("SAS_API_BASE_URL")
if not api_base_url:
    raise ValueError(
        "Defina a URL do backend do SAS via `cdk deploy -c apiBaseUrl=https://..." \
        "` ou na variável de ambiente SAS_API_BASE_URL (infra/.env)."
    )

scheduler_secret = os.environ.get("SAS_SCHEDULER_SECRET", "")
if not scheduler_secret:
    raise ValueError(
        "Defina SAS_SCHEDULER_SECRET no ambiente do deploy. O valor canônico "
        "mora no SSM: aws ssm get-parameter --name /sas/scheduler/secret "
        "--with-decryption --query Parameter.Value --output text"
    )

SasSchedulerStack(
    app,
    "SasSchedulerStack",
    api_base_url=api_base_url,
    scheduler_secret=scheduler_secret,
    env=cdk.Environment(
        account=os.environ.get("CDK_DEFAULT_ACCOUNT"),
        region=os.environ.get("CDK_DEFAULT_REGION"),
    ),
)

app.synth()
