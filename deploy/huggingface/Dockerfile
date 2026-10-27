# MDOS on a Hugging Face Space (Docker SDK). Runs the image that the "Container image" workflow publishes.
# Spaces run containers as user 1000, so the data folder is moved to a folder that user owns.
FROM ghcr.io/samuelhtampubolon/mdos:latest

USER root
RUN mkdir -p /home/mdos-data && chown 1000:1000 /home/mdos-data && chmod 700 /home/mdos-data
ENV MDOS_DATA_DIR=/home/mdos-data
USER 1000
