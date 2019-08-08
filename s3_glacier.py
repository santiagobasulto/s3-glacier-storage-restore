import time
import json
import logging
import functools

import click
import boto3
from botocore.exceptions import ClientError


class RestoreException(Exception):
    def __init__(self, msg, response=None):
        super().__init__(msg)
        self.response = response


class RestoreInProgressException(RestoreException):
    pass


class S3GlacierClient:
    def __init__(
        self,
        bucket,
        prefix="",
        default_restore_params=None,
        verbose=True,
        progress_logger=None,
        **boto_client_kwargs,
    ):
        self.s3_client = boto3.client("s3", **boto_client_kwargs)
        self.bucket = bucket
        self.prefix = prefix
        self.default_restore_params = default_restore_params or {}
        self.progress_logger = logging.getLogger("S3GlacierClient")
        self.progress_logger.setLevel(logging.INFO)
        if progress_logger:
            self.progress_logger = progress_logger
        elif verbose:
            ch = logging.StreamHandler()
            self.progress_logger.addHandler(ch)

    def log(self, level, *args):
        if self.progress_logger:
            getattr(self.progress_logger, level)(*args)

    debug = functools.partialmethod(log, "debug")
    info = functools.partialmethod(log, "info")

    def list_all_objects_from_bucket(self):
        kwargs = {"Bucket": self.bucket, "Prefix": self.prefix}
        while True:
            response = self.s3_client.list_objects_v2(**kwargs)
            yield from response.get("Contents", [])
            if not response.get("IsTruncated"):
                break
            continuation_token = response.get("NextContinuationToken")
            kwargs = {**kwargs, "ContinuationToken": continuation_token}

    def restore_object(self, key, restore_params=None):
        restore_params = {**self.default_restore_params, **(restore_params or {})}
        try:
            response = self.s3_client.restore_object(
                Bucket=self.bucket, Key=key, RestoreRequest=restore_params
            )
            status = response["ResponseMetadata"]["HTTPStatusCode"]
            if status > 400:
                self.info(
                    f"FAILED object restore failed: %s with response %s",
                    key,
                    e.response,
                )
                raise RestoreException("Invalid response status code", response)
            self.info(f"SUCCESS Restored object: %s", key)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code != "RestoreAlreadyInProgress":
                self.info(f"FAILED object restore in progress: %s", key)
                raise RestoreInProgressException("Restore in progress", e.response)
            self.info(
                f"FAILED object restore failed: %s with response %s", key, e.response
            )
            raise RestoreException(
                "Exception occurred while restoring. Check e.response", e.response
            ) from e

    def restore_objects_from_bucket(self, restore_params=None):
        restore_params = {**self.default_restore_params, **(restore_params or {})}
        results = {"successful": [], "restore_in_progress": [], "error": []}
        objects = self.list_all_objects_from_bucket()
        for obj in objects:
            key = obj["Key"]
            try:
                self.restore_object(key, restore_params)
                results["successful"].append(obj)
            except RestoreInProgressException:
                results["restore_in_progress"].append(obj)
            except RestoreException:
                results["error"].append(obj)
        return results

    def is_object_restored(self, key):
        response = self.s3_client.head_object(Bucket=self.bucket, Key=key)
        status = response["ResponseMetadata"]["HTTPHeaders"].get("x-amz-restore")
        return status != 'ongoing-request="true"'

    def are_objects_restored(self, sleep_in_seconds=60):
        objects = self.list_all_objects_from_bucket()
        for obj in objects:
            key = obj["Key"]
            while True:
                if self.is_object_restored(key):
                    break
                self.info("Restore in progress...")
                time.sleep(sleep_in_seconds)
        self.debug("Done!")


@click.group()
@click.option("-b", "--bucket", required=True)
@click.option("-p", "--prefix", default="")
@click.option("-q", "--quiet", default=True)
@click.option("--aws-access-key-id")
@click.option("--aws-secret-access-key")
@click.option("--aws-session-token")
@click.pass_context
def cli(
    ctx,
    bucket,
    prefix,
    quiet,
    aws_access_key_id,
    aws_secret_access_key,
    aws_session_token,
):
    ctx.ensure_object(dict)
    boto_kwargs = {
        "aws_access_key_id": aws_access_key_id,
        "aws_secret_access_key": aws_secret_access_key,
        "aws_session_token": aws_session_token,
    }
    ctx.obj["s3_client"] = S3GlacierClient(bucket, prefix, not quiet, **boto_kwargs)


@cli.command()
@click.argument("key")
@click.option("-d", "--days", default=3, type=int)
@click.option(
    "-t",
    "--tier",
    default="Standard",
    type=click.Choice(["Standard", "Bulk", "Expedited"]),
)
@click.pass_context
def restore_single_object(ctx, key, days, tier):
    restore_params = {"Days": days, "GlacierJobParameters": {"Tier": tier}}
    s3_client = ctx.obj["s3_client"]
    s3_client.restore_object(key, restore_params)


@cli.command()
@click.option("-d", "--days", default=3, type=int)
@click.option(
    "-t",
    "--tier",
    default="Standard",
    type=click.Choice(["Standard", "Bulk", "Expedited"]),
)
@click.pass_context
def restore_objects(ctx, days, tier):
    restore_params = {"Days": days, "GlacierJobParameters": {"Tier": tier}}
    s3_client = ctx.obj["s3_client"]
    s3_client.restore_objects_from_bucket(restore_params)


@cli.command()
@click.argument("key")
@click.pass_context
def is_object_restored(ctx, key):
    s3_client = ctx.obj["s3_client"]
    res = s3_client.is_object_restored(key)
    if res:
        click.echo("Object ready!")
    else:
        click.echo("Restore in progress...")


@cli.command()
@click.pass_context
def check_restore_status(ctx):
    s3_client = ctx.obj["s3_client"]
    click.echo(
        "Checking status of bucket. This operation can take some time if there are too many files."
    )
    s3_client.are_objects_restored()


if __name__ == "__main__":
    cli(obj={})
