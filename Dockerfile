# @intract.v1 scope:container intent:package:intract_cli priority:2 domain:runtime input:source_tree output:oci_image effect:build forbid:secret_leak,root_user,latest_tag validate:no_forbidden_effect meaning:"package Intract CLI as a safe container"
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -e .
USER 10001
ENTRYPOINT ["intract"]
CMD ["--help"]
