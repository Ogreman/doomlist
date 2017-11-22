FROM postgres:9.6.3

ENV POSTGRES_DB postgres
ENV POSTGRES_USER postgres

ADD groundzero.sql /docker-entrypoint-initdb.d/groundzero.sql
RUN chmod 755 /docker-entrypoint-initdb.d/groundzero.sql
