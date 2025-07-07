from neo4j import GraphDatabase

uri = "neo4j://127.0.0.1:7687"
username = "neo4j"
password = "JUcvo0027"

driver = GraphDatabase.driver(uri, auth=(username, password))

with driver.session() as session:
    result = session.run("RETURN 1 AS result")
    for record in result:
        print(record["result"])