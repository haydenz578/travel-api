![Swagger](https://img.shields.io/badge/-Swagger-%23Clojure?logo=swagger&logoColor=white)
[![API Documentation](https://img.shields.io/badge/API-Documentation-blue)](https://haydenz578.github.io/BerlinTravelAPI/#/)
![Flask](https://img.shields.io/badge/flask-%23000.svg?logo=flask&logoColor=white)
![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)

# Berlin Travel API

## 📖 Overview
Berlin Travel API provides public transport travel information and operator data for Berlin and Brandenburg.  
It is containerized using Docker and built automatically via a CI/CD pipeline powered by GitHub Actions.

## :camera_flash: Features
- RESTful API with full CRUD operations for public transport stops
- Travel guidance provided by AI based on user data
- Swagger UI documentation for easy testing and exploration
- Containerized using Docker for consistent deployment
- Automated CI/CD pipeline that builds and pushes Docker images to Docker Hub
- Secure handling of API keys and environment variables via GitHub Secrets

## :card_file_box: Tech Stack
| Category	| Technology |
| --------- | ---------- |
| Language	| Python |
| Framework |	Flask |
| Database | SQLite |
| AI service | Google Gemini |
| Documentation	| Swagger (OpenAPI 2.0) |
| Containerization | Docker |
| CI/CD	| GitHub Actions |
| Secrets Management | GitHub Secrets |

## :bookmark_tabs: API Documentation
### :clapper: Preview
<img width="944" height="416" alt="api" src="https://github.com/user-attachments/assets/da3b4c55-65b8-428d-b83e-c406f5185d26" />

#### 👉 [View Interactive API Documentation Here](https://haydenz578.github.io/BerlinTravelAPI/#/)

## 🐳 Local Docker Setup
You can build and run this API locally:
### :one: 
Get a Google Gemini API key and clone this repo to your local machine
### :two: 
```
docker build -t berlin-travel-api .
```
### :three:
```
docker run -d -p 5000:5000 \
  -e Google_API_KEY=<your_google_api_key> \
  berlin-travel-api
```
