import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

POLICY_DOCS: list[dict[str, str]] = [
    {
        "title": "PM-KISAN",
        "content": "Provides Rs 6000 per year in 3 DBT installments to eligible landholding farmer families linked with Aadhaar.",
        "source": "PM-KISAN guidelines",
        "tags": "income assistance dbt aadhaar landholding punjab",
    },
    {
        "title": "PMFBY Crop Insurance",
        "content": "Covers yield losses due to drought, flood, pests, diseases, and post-harvest losses up to 14 days. Premium rates include 2 percent for Kharif and 1.5 percent for Rabi.",
        "source": "PMFBY operational manual",
        "tags": "insurance kharif rabi paddy wheat loss weather pest disease",
    },
    {
        "title": "Kisan Credit Card",
        "content": "Provides short-term working capital for seeds, fertilizers, pesticides, and allied activities. Timely repayment can reduce effective interest burden.",
        "source": "KCC RBI/NABARD framework",
        "tags": "credit loan fertilizer seed pesticide interest working capital",
    },
    {
        "title": "PM Kisan Maandhan Yojana",
        "content": "Voluntary pension for small and marginal farmers aged 18-40, with matching government contribution and pension at age 60.",
        "source": "PM Kisan Maandhan Yojana document",
        "tags": "pension social security small marginal farmer",
    },
    {
        "title": "PMKSY Per Drop More Crop",
        "content": "Promotes micro-irrigation, including drip and sprinkler systems, and supports water conservation and watershed development.",
        "source": "PMKSY operational guidelines",
        "tags": "irrigation drip sprinkler water conservation groundwater punjab",
    },
    {
        "title": "Agriculture Infrastructure Fund",
        "content": "Supports medium and long-term debt with interest subvention and credit guarantee for warehouses, cold storage, grading and processing infrastructure.",
        "source": "AIF scheme framework",
        "tags": "infrastructure warehouse cold storage processing fpo",
    },
    {
        "title": "Soil Health Card Scheme",
        "content": "Provides soil testing every 2 years and crop-wise nutrient recommendations including NPK and micronutrients.",
        "source": "Soil Health Card Scheme",
        "tags": "soil fertility nutrient npk micronutrient urea",
    },
    {
        "title": "PKVY Organic Farming",
        "content": "Supports cluster-based organic farming, including assistance for inputs, certification, and marketing.",
        "source": "PKVY guidelines",
        "tags": "organic cluster certification sustainability",
    },
    {
        "title": "NMSA",
        "content": "Promotes climate-resilient agriculture, efficient water use, soil conservation, and rainfed area development.",
        "source": "NMSA mission document",
        "tags": "climate resilience soil water sustainability",
    },
    {
        "title": "MSP Framework",
        "content": "Provides pre-declared price support and procurement for major crops. In Punjab, wheat and paddy procurement strongly affects cropping decisions.",
        "source": "MSP policy framework",
        "tags": "msp paddy wheat procurement diversification income",
    },
    {
        "title": "e-NAM",
        "content": "Online mandi integration platform for better price discovery and wider market access.",
        "source": "e-NAM framework",
        "tags": "market mandi pricing digital trading",
    },
    {
        "title": "NFSM",
        "content": "Promotes productivity in rice, wheat, and pulses using improved seeds, demonstrations, and targeted support.",
        "source": "NFSM documents",
        "tags": "rice wheat pulse productivity seed",
    },
    {
        "title": "Digital Agriculture Mission",
        "content": "Supports AgriStack, digital farmer records, AI advisories, remote sensing, and precision agriculture.",
        "source": "Digital Agriculture Mission",
        "tags": "digital agristack ai precision satellite",
    },
    {
        "title": "SMAM",
        "content": "Provides machinery subsidies, often 40-80 percent, including Happy Seeder and other mechanization tools.",
        "source": "SMAM guidelines",
        "tags": "mechanization happy seeder subsidy stubble",
    },
    {
        "title": "National Livestock Mission",
        "content": "Supports fodder, breed improvement, and livestock productivity improvements.",
        "source": "National Livestock Mission",
        "tags": "dairy livestock fodder breed allied income",
    },
    {
        "title": "PMMSY",
        "content": "Promotes fisheries infrastructure, cold chain, aquaculture productivity, and value chain development.",
        "source": "PMMSY scheme",
        "tags": "fisheries aquaculture cold chain allied sector",
    },
    {
        "title": "DEDS",
        "content": "Supports dairy entrepreneurship, milk processing, and value-addition with capital subsidy support.",
        "source": "DEDS guidelines",
        "tags": "dairy entrepreneurship processing subsidy",
    },
]

# Pre-compute TF-IDF matrix at module load time for fast query-time retrieval.
# Each document is the concatenation of its title, content, and tags so all
# fields contribute to relevance scoring.
_corpus = [
    f"{d['title']} {d['content']} {d['tags']}"
    for d in POLICY_DOCS
]
_vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
_tfidf_matrix = _vectorizer.fit_transform(_corpus)


def retrieve_policy_context(query: str, top_k: int = 4) -> list[dict[str, str]]:
    if not query or not query.strip():
        return []
    query_vec = _vectorizer.transform([query.lower()])
    scores = cosine_similarity(query_vec, _tfidf_matrix).flatten()
    top_indices = np.argsort(scores)[::-1][:top_k]
    return [POLICY_DOCS[i] for i in top_indices if scores[i] > 0.0]
