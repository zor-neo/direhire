FROM ghcr.io/astral-sh/uv:0.8.15 AS uv

FROM public.ecr.aws/lambda/python:3.13

COPY --from=uv /uv /bin/uv
COPY pyproject.toml /tmp/direhire/pyproject.toml
COPY uv.lock /tmp/direhire/uv.lock
COPY apps/api/src /tmp/direhire/apps/api/src
RUN cd /tmp/direhire \
    && /bin/uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file requirements.txt \
    && pip install --no-cache-dir --requirement requirements.txt \
    && pip install --no-cache-dir --no-deps /tmp/direhire \
    && rm -rf /tmp/direhire

CMD ["direhire.main.handler"]
