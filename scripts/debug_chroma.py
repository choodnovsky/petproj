import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)

collections = client.list_collections()
cllist =[c.name for c in  collections]
print(cllist)

print("Коллекции:")
for c in collections:
    print("-", c.name)

print("\nДокументы в коллекции 'wiki_docs':")
collection = client.get_collection("wiki_docs")
results = collection.get(include=["documents"])

for i, doc in enumerate(results["documents"]):
    print(f"\nchunk_{i}:\n{doc[:500]}...")