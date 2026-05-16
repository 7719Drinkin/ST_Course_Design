# AUT Risk Mitigation Strategy Draft

本文档可作为 Risk Analysis Report §4 的初始草稿。描述对象是 AUT `LibraryManagementSystem` 的功能风险，不是 AutoTestDesign 工具风险。

## 1. High-Risk Areas

| AUT Area | Risk | Impact | Mitigation |
|---|---|---|---|
| Borrowing | Borrowing a book with no available copies | Inventory may become negative or inconsistent | BVA test for `availableCopies = 0`; DT rule for no-copy rejection; assert HTTP 400 |
| Borrowing | Invalid `book.id` or `member.id` accepted | Borrowing record may reference non-existing resources | EP tests for missing/unknown IDs; assert no borrowing record is created |
| Return | Duplicate return accepted | Inventory may be incremented multiple times | FSM transition test: Borrowed -> Returned -> duplicate return rejected |
| Return | Unknown `recordId` accepted | Invalid state transition | Negative EP test for missing record; assert HTTP 400 |
| Records | Borrowing records list inconsistent with operations | Audit trail cannot be trusted | Integration flow test: create borrow record, query list, verify record exists |
| Error Handling | Malformed JSON accepted or crashes service | API robustness issue | Negative JSON request test; assert HTTP 400 |
| Data Persistence | In-memory storage loses data on restart | Test data cannot be assumed stable | Each test creates its own data; no test depends on previous AUT run |
| Validation | No Bean Validation on model fields | Some invalid payloads may be accepted | Document known limitation; avoid claiming validation that AUT does not implement |

## 2. Testing Response

| Risk Type | Testing Technique |
|---|---|
| Valid vs invalid resource IDs | Equivalence Partitioning |
| Available copies boundary | Boundary Value Analysis |
| Borrowing decision rules | Decision Table |
| Borrow / return lifecycle | FSM state transition |
| Export and generated case traceability | Contract checks |

## 3. Required Evidence

Risk mitigation claims should be backed by:

- pytest result;
- requirement ID;
- test case ID;
- endpoint;
- expected status code;
- actual status code;
- owner for failures.

## 4. Pending Inputs

This draft still needs B's risk matrix:

| Required Input | Owner | Usage |
|---|---|---|
| impact score | B | Risk priority |
| likelihood score | B | Risk priority |
| H/M/L level | B | Risk heatmap and mitigation order |
| retrieved standard references | B | Evidence for selected test technique |
