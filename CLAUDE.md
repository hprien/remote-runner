# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Remote-runner is a service that offers script execution via REST API. It provides a REST API through which clients can request script execution. The folder `scripts` contains a subfolder for each script. A executable file with the same name as the folder is supposed to be In every of these subfolders folders.

## Architecture

Key architectural considerations:
- REST API - python fastapi
- python backend runs with root permission
- python backend executes scripts with root permission
- the std out and err out and return code of the execution will be send to a webhook
- .env file with port and api key

## usage

there is supposed to be one api route that take:
- the script name (subfolder of `scripts`)
- output_webhook (results will go here)
- Authorization headeer with Bearer token