# Cloud Service Access Management System

This repository contains a FastAPI backend for managing user access to cloud services based on subscription plans. It includes:
- **Plan management** (create, modify, delete plans with permissions and usage limits)  
- **Permission management** (add, modify, remove API permissions)  
- **User subscriptions** (subscribe to, view, and modify plans)  
- **Access control & usage tracking** (check permissions, enforce call limits)  
- **Service endpoints** (to simulate protected cloud APIs)  

---

## Table of Contents

1. [Prerequisites](#prerequisites)  
2. [Installation](#installation)  
3. [Running the App](#running-the-app)  
4. [API Endpoints](#api-endpoints)  
   - [Plans](#plans)  
   - [Permissions](#permissions)  
   - [Subscriptions](#subscriptions)  
   - [Usage & Access Control](#usage--access-control)  
   - [Services](#services)  
5. [Testing](#testing)  
6. [Project Structure](#project-structure)  
7. [Team Members](#team-members)  

---

## Prerequisites

- Python 3.8+  
- SQLite (bundled with Python)  

## Installation

1. Clone the repository:  
        git clone <your-repo-url>  
        cd <repo-folder>  

2. Create and activate a virtual environment:  
        python3 -m venv venv  
        source venv/bin/activate    # on macOS/Linux  
        venv\Scripts\activate       # on Windows  

3. Install dependencies:  
        pip install --upgrade pip  
        pip install -r requirements.txt  

## Running the App

Start the FastAPI server using Uvicorn:  
        uvicorn main:app --reload  

By default, it listens on `http://127.0.0.1:8000`. You can view the automatic API docs at:  
- Swagger UI: `http://127.0.0.1:8000/docs`  
- ReDoc:     `http://127.0.0.1:8000/redoc`  

## API Endpoints

### Plans

- **Create Plan**  
  - `POST /plans`  
  - Request body example:  
        {
          "name": "Basic",
          "description": "Basic access plan",
          "permission_ids": [1,2],
          "limits": [100,10]
        }
  - Response example:  
        { "id": 3 }

- **Modify Plan**  
  - `PUT /plans/{plan_id}`  
  - Request body example:  
        {
          "name": "Pro",
          "permission_ids": [1,3],
          "limits": [200,5]
        }
  - Response example:  
        { "status": "updated" }

- **Delete Plan**  
  - `DELETE /plans/{plan_id}`  
  - Response example:  
        { "status": "deleted" }

### Permissions

- **Add Permission**  
  - `POST /permissions`  
  - Request body example:  
        {
          "name": "read_data",
          "endpoint": "service1",
          "description": "Read-only access"
        }
  - Response example:  
        { "id": 1 }

- **Modify Permission**  
  - `PUT /permissions/{permission_id}`  
  - Request body example:  
        { "endpoint": "service1_v2" }
  - Response example:  
        { "status": "updated" }

- **Delete Permission**  
  - `DELETE /permissions/{permission_id}`  
  - Response example:  
        { "status": "deleted" }

### Subscriptions

- **Subscribe to Plan**  
  - `POST /subscriptions`  
  - Request body example:  
        { "user_id": 42, "plan_id": 3 }
  - Response example:  
        { "status": "subscribed" }

- **View Subscription**  
  - `GET /subscriptions/{user_id}`  
  - Response example:  
        {
          "user_id": 42,
          "plan": { "id": 3, "name": "Basic", "description": "..." },
          "permissions": [
            { "permission_id": 1, "endpoint": "service1", "limit": 100 }
          ]
        }

- **View Usage Stats**  
  - `GET /subscriptions/{user_id}/usage`  
  - Response example:  
        { "user_id": 42, "usage": [ { "endpoint": "service1", "count": 5 } ] }

- **Modify Subscription**  
  - `PUT /subscriptions/{user_id}`  
  - Request body example:  
        { "user_id": 42, "plan_id": 2 }
  - Response example:  
        { "status": "updated" }

### Usage & Access Control

- **Check Access**  
  - `GET /access/{user_id}/{endpoint}`  
  - Response example:  
        { "user_id": 42, "endpoint": "service1", "access": true, "reason": null }

- **Record Usage**  
  - `POST /usage/{user_id}`  
  - Request body example:  
        { "endpoint": "service1" }
  - Response example:  
        { "status": "recorded" }

- **Limit Status**  
  - `GET /usage/{user_id}/limit`  
  - Response example:  
        {
          "user_id": 42,
          "limits": [ { "endpoint": "service1", "used": 5, "limit": 100 } ]
        }

### Services

Simulated service endpoints that enforce access rules:

- **Call Service**  
  - `GET /services/{service_name}`  
  - Query parameter: `user_id`  
  - Example request:  
        GET /services/service1?user_id=42  
  - Successful response example:  
        { "service": "service1", "status": "OK" }
  - Errors:  
    - 404 if service not found  
    - 403 if usage limit reached or no permission  

## Testing

Run the pytest suite to verify all endpoints and logic:  
        pytest tests/test_api.py -q -s  

Ensure you have `aiosqlite` installed so the async SQLite driver works.

## Project Structure

    main.py               # FastAPI application
    requirements.txt      # Python dependencies
    tests/
    └── test_api.py       # pytest suite
    README.md             # This file

## Team Member

- Khushi Kaushik 
