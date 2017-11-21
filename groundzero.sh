#!/bin/bash
docker exec postgres psql -U postgres -f /docker-entrypoint-initdb.d/groundzero.sql