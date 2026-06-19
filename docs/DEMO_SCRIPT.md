# Live Demonstration Script

Follow this step-by-step script to execute a live demonstration of the EconIQ platform using the seeded showcase customers.

---

## Pre-Demo Setup Verification
1. Ensure the PostgreSQL database is online and fully seeded by running the seeder:
   ```bash
   .venv/bin/python seed_demo_customers.py
   ```
2. Confirm the FastAPI backend is running on `http://localhost:8000`.
3. Confirm the Next.js frontend is running on `http://localhost:3000`.

---

## Step 1: System Vitals Dashboard
- **Navigation:** Open browser to `http://localhost:3000/dashboard`.
- **Narrative:** 
  > *"Welcome to EconIQ—a Stateful Commercial Decision Intelligence Platform. Here on the Dashboard, credit analysts get a high-level view of our commercial risk. Notice the Total Outstanding Exposure card displaying our active billing ledger status, the Aging Overdue Distribution tracking invoice lateness, and the Active System Alerts highlighting accounts that require immediate attention."*
- **Action:** Point out the active critical alert from **Deccan Logistics Ltd** under the notification sidebar.

---

## Step 2: The Customers Matrix Grid
- **Navigation:** Click **Matrix** in the navigation bar to go to `/customers`.
- **Action:** 
  1. In the search box, type `Titan` to filter **Titan B2B Industries** (our Whale account). Note its High Health Score (`0.92`) and Elite state.
  2. Clear the search and select **declining** from the state filter dropdown. **Deccan Logistics Ltd** (our Distressed account) appears.
- **Narrative:**
  > *"The Matrix displays all accounts mapped to their behavioral states. We can filter accounts by delinquency state, search by customer names, or sort by trust and risk scores to decide where to focus collections outreach."*

---

## Step 3: Analytical Dossier (Deccan Logistics Ltd)
- **Navigation:** In the Matrix grid, click on the **Deccan Logistics Ltd** row (or navigate directly to `/customer/00000000-0000-0000-0000-000000000002`).
- **Narrative:**
  > *"Let's drill down into Deccan Logistics, our distressed account. The header vitals ribbon immediately alerts us that this customer is in a declining state, with a health score of 0.31, distress risk of 89%, and INR 840,000 outstanding."*
- **Action:** Scroll down to the **Behavioral Memory Timeline** card. Point out the lack of payment events in the last 90 days.

---

## Step 4: Explainability & Counterfactual Simulator
- **Navigation:** Click on the **ML Cockpit** tab in the dossier workspace.
- **Action:** 
  1. Examine the **SHAP Explanation Factors** bar chart. Point out the negative indicators (red bars) representing low payment discipline and high average delay.
  2. Scroll down to the **What-If Simulation Engine**. Select the actions **LOG_OUTREACH_CALL** and **REVISE_CREDIT_Horiz_60D**. Click **Compute Simulation**.
- **Narrative:**
  > *"Why is Deccan Logistics at risk? The SHAP chart shows that payment discipline and terms compliance are pulling down their score. Using the Simulation Cockpit, we can test hypothetical actions. If we log an outreach call and adjust their credit limit window, our XGBoost simulator predicts that their default risk drops from 89% down to 41%, improving their health score. This enables us to test credit adjustments digitally before executing them."*

---

## Step 5: Log Collections Outreach
- **Navigation:** Scroll to the **Operations Panel** on the right.
- **Action:**
  1. Under **Log Collections Outreach**, select activity type **CALL** and outcome **PROMISE_MADE**.
  2. In the notes, type: `Called manager. Promised to settle outstanding balance by next Friday.` Click **Log Outreach**.
- **Narrative:**
  > *"Having simulated a positive outcome, we execute the contact. We log the phone outreach directly in the CRM widget. This saves the log into Postgres and appends it to the customer timeline."*

---

## Step 6: Log Payment Commitment
- **Navigation:** Scroll to the **Commitment Form** in the operations panel.
- **Action:**
  1. Input Amount: `500000` (INR 500,000).
  2. Select Date: Choose next Friday's date. Click **Log Commitment**.
- **Narrative:**
  > *"Along with logging the call, the customer promised to pay INR 500,000. We log this payment commitment to track if they keep this promise next week."*

---

## Step 7: Log Override Decision
- **Navigation:** Scroll to the **Advisor Cockpit** showing the recommendation `CREDIT_HOLD`.
- **Action:**
  1. Click **Override Action**. Select action **OVERRIDDEN**.
  2. Type justification: `Overriding credit hold because client registered a formal INR 500,000 payment commitment.` Click **Submit Decision**.
- **Narrative:**
  > *"Finally, we look at the Advisor recommendation. It suggests putting Deccan Logistics on a credit hold. However, because they just registered a formal payment commitment of INR 500,000, we choose to override the hold. We submit our justification, creating a permanent audit trail for compliance."*
