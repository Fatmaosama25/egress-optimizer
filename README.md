# DevOps Automation for Cloud Egress Cost Optimization

A **5-Layer Automated DevOps Framework** for optimizing cloud egress costs through intelligent data classification and migration.

## 🎯 Problem

Organizations pay significant cloud egress fees ($0.09/GB) when frequently accessing data stored in the cloud. This framework automatically identifies which data should be stored locally vs. in the cloud to minimize costs.

## 🏗️ Architecture — 5-Layer Framework

| Layer | Purpose | Tools |
|-------|---------|-------|
| **Layer 1** | Monitor & Collect | Python, boto3, CloudWatch |
| **Layer 2** | Classify & Analyze | scikit-learn ML, Cost Engine |
| **Layer 3** | Optimize Migrations | Cost-benefit algorithms |
| **Layer 4** | Generate IaC | Terraform (.tf files) |
| **Layer 5** | CI/CD & Deploy | GitHub Actions |

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Docker Desktop
- Terraform
- Git

### Setup
```bash
# Clone the repository
git clone <your-repo-url>
cd egress-optimizer

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Start LocalStack + MinIO
docker-compose up -d

# Run the pipeline
python src/main.py
```

## 📁 Project Structure

```
egress-optimizer/
├── config/config.yaml           # Thresholds & pricing
├── src/
│   ├── main.py                  # Pipeline orchestrator
│   ├── collector/               # Layer 1: Data collection
│   ├── analyzer/                # Layer 2: Cost analysis
│   ├── classifier/              # Layer 2: ML classification
│   ├── optimizer/               # Layer 3: Migration decisions
│   ├── iac_generator/           # Layer 4: Terraform generation
│   └── monitor/                 # Savings tracking
├── terraform/                   # Generated Terraform configs
├── dashboard/                   # Web dashboard
├── tests/                       # pytest tests
├── docker-compose.yml           # LocalStack + MinIO
└── requirements.txt             # Python dependencies
```

## 📊 Key Results

- **40-60% cost reduction** in cloud egress fees
- **< 6 month payback** period for local server investment
- **> 90% accuracy** in Hot/Warm/Cold/Archive classification

## 📝 Thesis

**Master's Thesis** — Thebes Academy, Faculty of Computers and Informatics

**Title:** DevOps Automation for Cloud Egress Cost Optimization

**Author:** Fatma
