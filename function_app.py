"""Fishadoo Azure Function App

Entry point for all Azure Functions in this project.  Each function is
registered on the ``app`` object using the Azure Functions Python v2
programming model.

Environment variables consumed by this module
---------------------------------------------
SCHEDULE
    A six-field CRON expression (seconds field included) that controls how
    often the timer fires.  Example: ``0 */10 * * * *`` (every 10 minutes).
    Set this in ``local.settings.json`` for local development and in the
    Function App configuration blade (or Bicep parameters) for Azure.

TABLE_ACCOUNT_NAME
    **Preferred in Azure.**  Storage account name.  When set, the function
    authenticates via ``DefaultAzureCredential`` (managed identity in Azure,
    ``az login`` locally).  No connection string or shared key is required.

TABLE_CONNECTION_STRING
    **Local development only.**  Azure Storage connection string.  Use
    ``UseDevelopmentStorage=true`` when running against Azurite locally.
    If ``TABLE_ACCOUNT_NAME`` is set, this variable is ignored.

TABLE_NAME
    Optional.  Name of the Azure Storage table to write to.
    Defaults to ``RandomStrings``.

APPLICATIONINSIGHTS_CONNECTION_STRING
    Optional.  When set, telemetry is forwarded to Application Insights
    automatically by the Azure Functions host.
"""

import logging

import azure.functions as func

from shared.table_writer import write_random_string

logger = logging.getLogger(__name__)

app = func.FunctionApp()


@app.timer_trigger(
    schedule="%SCHEDULE%",
    arg_name="timer",
    run_on_startup=False,
    use_monitor=True,
)
def random_string_writer(timer: func.TimerRequest) -> None:
    """Timer-triggered function that writes a random string to Azure Table Storage.

    Fires on the schedule defined by the ``SCHEDULE`` app setting (default:
    every 10 minutes).  If the previous run was missed, ``timer.past_due``
    will be ``True`` and a warning is emitted so the anomaly is visible in
    Application Insights / Log Analytics.
    """
    if timer.past_due:
        logger.warning(
            "Timer is past due – the previous scheduled execution was missed. "
            "Check the Function App scaling and host health."
        )

    logger.info("random_string_writer triggered.")

    try:
        write_random_string()
    except ValueError as exc:
        # Configuration error (e.g. missing env var) – surface clearly in logs.
        logger.critical(
            "Configuration error – function cannot run until this is resolved: %s",
            exc,
        )
        raise
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Unexpected error in random_string_writer: %s", exc, exc_info=True
        )
        raise

    logger.info("random_string_writer completed successfully.")
