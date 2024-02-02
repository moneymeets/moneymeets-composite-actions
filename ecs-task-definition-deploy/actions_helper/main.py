import logging
import os
from dataclasses import dataclass

import boto3
import click
from botocore.client import BaseClient


class NonSingleValueError(Exception):
    pass


@dataclass
class Tag:
    key: str
    value: str


def get_tags(task_definition_tags: str) -> tuple[Tag, ...]:
    try:
        return tuple(
            Tag(tag.strip().split(":")[0], tag.strip().split(":")[1])
            for tag in task_definition_tags.split(",")
        )
    except IndexError:
        raise ValueError(
            "Invalid task definition tag format, expects 'key:value,key:value'"
        )


def get_active_task_definition_arn_by_tag(
    *,
    task_definition_family_prefix: str,
    task_definition_tags: str,
    allow_empty: bool,
) -> str:
    ecs_client: BaseClient = boto3.Session(region_name="eu-central-1").client("ecs")

    tags = get_tags(task_definition_tags)

    active_task_definition_arns = ecs_client.list_task_definitions(
        familyPrefix=task_definition_family_prefix,
        status="ACTIVE",
        sort="DESC",
    )["taskDefinitionArns"]

    active_task_definitions = [
        task_definition["taskDefinition"]["taskDefinitionArn"]
        for task_definition_arn in active_task_definition_arns
        if (
            task_definition := ecs_client.describe_task_definition(
                taskDefinition=task_definition_arn,
                include=["TAGS"],
            )
        )
        and all(
            {"key": tag.key, "value": tag.value} in task_definition["tags"]
            for tag in tags
        )
    ]

    if allow_empty and not active_task_definitions:
        return ""

    try:
        (task_definition,) = active_task_definitions
        return task_definition
    except ValueError as e:
        raise NonSingleValueError(
            f"Expected exactly one active task definition with tags {task_definition_tags}. "
            f"Found: {active_task_definitions}",
        ) from e


@click.group()
def cli():
    pass


@cli.command(
    name="get-active-task-definition-arn-by-tag",
    short_help="Get active task definition ARN  by specified tags",
)
@click.option("--application-id", default=os.environ.get("APPLICATION_ID"), type=str)
@click.option("--tags", default=os.environ.get("TAGS"), type=str)
@click.option("--allow-empty", is_flag=True, default=False)
def cmd_get_active_task_definition_arn_by_tag(
    application_id: str, tags: str, allow_empty: bool
):
    click.echo(
        get_active_task_definition_arn_by_tag(
            task_definition_family_prefix=application_id,
            task_definition_tags=tags,
            allow_empty=allow_empty,
        )
    )


if __name__ == "__main__":
    cli()
