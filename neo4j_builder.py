import json
from neo4j import GraphDatabase

uri = "neo4j://127.0.0.1:7687"
username = "neo4j"
password = "JUcvo0027"

driver = GraphDatabase.driver(uri, auth=(username, password))

with open("/Users/yunanli/Desktop/MasterThesis/MemoryGraph/generated_graph.json") as f:
    data = json.load(f)

def insert_r_graph(tx, r_graph):
    for edge in r_graph:
        E1 = edge["E1"]
        E2 = edge["E2"]
        for rel in edge["R"]:
            time = rel["time"]
            relationship = rel["relationship"]
            event = rel["event"]


            tx.run(
                """
                MERGE (a:Entity {name: $E1})
                MERGE (b:Entity {name: $E2})
                MERGE (a)-[r:RELATED_TO {
                    time: $time,
                    relationship: $relationship,
                    event: $event
                }]->(b)
                """,
                E1=E1,
                E2=E2,
                time=time,
                relationship=relationship,
                event=event,
            )

def insert_l_graph(tx, l_graph):
    for entry in l_graph:
        label = entry["Label"]
        entity = entry["Entity"]
        time = entry["time"]

        # Cypher：创建 Label 节点、Entity 节点，连接关系
        tx.run(
            """
            MERGE (l:Label {name: $label})
            MERGE (e:Entity {name: $entity})
            MERGE (l)-[r:ASSOCIATED_WITH {time: $time}]->(e)
            """,
            label=label,
            entity=entity,
            time=time,
        )

# 写入 Neo4j
with driver.session() as session:
    session.write_transaction(insert_r_graph, data["R"])
    session.write_transaction(insert_l_graph, data["L"])

print("Graph data imported to Neo4j!")
