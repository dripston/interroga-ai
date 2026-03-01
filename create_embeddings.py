# create_rag_index.py
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document
import json

print("📂 Loading mystery cases...")
with open("playful_mysteries_100.json", "r", encoding="utf-8") as f:
    cases = json.load(f)

print(f"✅ Loaded {len(cases)} cases")

# Convert each case to a document
documents = []
for case in cases:
    # Convert case to text format for embedding
    if "case" in case:  # Successfully parsed cases
        case_data = case["case"]
        
        # Create a comprehensive text representation
        text = f"""
Title: {case_data.get('title', 'Unknown')}
Difficulty: {case.get('difficulty', 'unknown')}
Setting: {case_data.get('setting', 'Unknown')}
Crime: {case_data.get('crime', 'Unknown')}

Suspects: {json.dumps(case_data.get('suspects', []), indent=2)}

Evidence: {json.dumps(case_data.get('evidence', []), indent=2)}

Timeline: {json.dumps(case_data.get('timeline', []), indent=2)}

Solution: {json.dumps(case_data.get('solution', {}), indent=2)}
"""
        
        documents.append(Document(
            page_content=text,
            metadata={
                "id": case.get("id"),
                "difficulty": case.get("difficulty"),
                "theme": case.get("theme"),
                "crime_type": case.get("crime_type")
            }
        ))
    elif "raw_response" in case:  # Cases with parse errors
        documents.append(Document(
            page_content=case["raw_response"],
            metadata={
                "id": case.get("id"),
                "difficulty": case.get("difficulty"),
                "parse_error": True
            }
        ))

print(f"📄 Created {len(documents)} documents")

# Optional: Split long documents into chunks
# (Usually not needed for mystery cases since they're already structured)
print("✂️  Splitting documents (if needed)...")
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=2000,  # Larger chunks for mystery cases
    chunk_overlap=200,
    separators=["\n\n", "\n", " ", ""]
)
split_docs = text_splitter.split_documents(documents)
print(f"📦 Split into {len(split_docs)} chunks")

# Create embeddings
print("🧠 Creating embeddings (this takes ~5-10 min)...")
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'}  # Use 'cuda' if you have GPU
)

# Create vector store
print("💾 Building FAISS index...")
vectorstore = FAISS.from_documents(split_docs, embeddings)

# Save to disk
print("💾 Saving index...")
vectorstore.save_local("mystery_rag_index")

print("\n✅ RAG index created successfully!")
print(f"📊 Total documents indexed: {len(split_docs)}")
print(f"📁 Saved to: mystery_rag_index/")