# System Design & Known Limitations

This document lists known limitations and architectural decisions in the current EconIQ platform version.

---

## 1. Counterfactual Simulation
- **Current Behavior:** What-if simulation outputs are computed using a statistical heuristic model inside [CounterfactualSimulator](file:///home/sugarcube/Desktop/Documents/Code-Server/Hackathon%20Projects/India-Runs/ECON-IQ/Econ-Core/core/ml/simulator/simulator.py).
- **Reasoning:** Re-running full ML training pipelines on-the-fly for every UI slider event is resource-intensive and slow. The heuristic model provides instant feedback (<15ms response times) for credit manager testing.
- **Future Improvement:** Deploy lightweight surrogate models (e.g. neural network approximations of the XGBoost boundary) to achieve real-time inference during simulations.

---

## 2. client-Side Timeline Aggregation
- **Current Behavior:** Customer timelines are constructed on the client by merging ledger events, logged outreach attempts, and payment promises.
- **Reasoning:** Offloads sorting and rendering calculations to the browser, reducing database query overhead.
- **Future Improvement:** Build a pre-joined, indexed view in Postgres to stream unified event feeds.

---

## 3. Data Ingestion Polling Interval
- **Current Behavior:** The database sync worker checks for new sales, payments, or returns every 10 seconds.
- **Reasoning:** Standard development database polling.
- **Future Improvement:** Replace polling with PostgreSQL write-ahead log (WAL) streams or event broker queues (e.g., Apache Kafka / RabbitMQ) to enable real-time dashboard updates.

---

## 4. User Authentication OTP Mode
- **Current Behavior:** Logins utilize a preconfigured mock OTP password (`735011`) for review and judge walkthrough convenience.
- **Reasoning:** Simplifies the hackathon demonstration workflow by removing external SMTP email requirements.
- **Future Improvement:** Integrate production identity systems (e.g., Auth0, Clerk, or AWS Cognito) for multi-factor authentication (MFA).
