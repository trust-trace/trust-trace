FROM neo4j:5.26-community

ENV NEO4J_AUTH=neo4j/trusttrace \
    NEO4J_server_memory_heap_initial__size=512m \
    NEO4J_server_memory_heap_max__size=1G \
    NEO4J_dbms_memory_pagecache_size=512m

COPY migrations/ /var/lib/neo4j/migrations/
COPY init.sh /startup/init.sh
RUN chmod +x /startup/init.sh

EXPOSE 7474 7687

ENTRYPOINT ["/startup/init.sh"]
