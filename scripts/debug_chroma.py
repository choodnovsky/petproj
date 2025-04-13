import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)

collections = client.list_collections()
print("🔍 Коллекции:")
for c in collections:
    print("-", c.name)

print("\n📄 Документы в коллекции 'wiki_docs':")
collection = client.get_collection("wiki_docs")
results = collection.get(include=["documents"])  # Убрали "ids"

for i, doc in enumerate(results["documents"]):
    print(f"\n🧱 chunk_{i}:\n{doc[:500]}...")