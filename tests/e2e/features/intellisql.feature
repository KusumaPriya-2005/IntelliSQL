Feature: IntelliSQL - Intelligent Query Assistance
  As a user
  I want to query a local SQLite database using natural language
  So that I can retrieve results safely (read-only) and see helpful validation messages

  Background:
    Given the IntelliSQL app is running

  Scenario: Show database initialization banner when DB is missing
    Given the database file does not exist
    When I open the "Intelligent Query Assistance" page
    Then I should see a warning that the database is not found
    And I should see an "Initialize database" button

  Scenario: Initialize database successfully from the UI
    Given the database file does not exist
    When I open the "Intelligent Query Assistance" page
    And I click the "Initialize database" button
    Then I should see a success message that the database is initialized
    And I should see a "Database schema" expander

  Scenario: Require API key before submitting
    Given the database is initialized
    And the GOOGLE_API_KEY is not configured
    When I open the "Intelligent Query Assistance" page
    And I enter "Show all students" in the query input
    And I click the "Get Answer" button
    Then I should see an error message about missing GOOGLE_API_KEY

  Scenario: Require a non-empty question
    Given the database is initialized
    And the GOOGLE_API_KEY is configured
    When I open the "Intelligent Query Assistance" page
    And I click the "Get Answer" button
    Then I should see a warning asking me to enter a question

  Scenario: Block unsafe generated SQL
    Given the database is initialized
    And the GOOGLE_API_KEY is configured
    And the model generates the SQL "DROP TABLE students"
    When I open the "Intelligent Query Assistance" page
    And I enter "Delete the students table" in the query input
    And I click the "Get Answer" button
    Then I should see a "Query blocked" message
    And I should see the reason explaining that only read-only SELECT queries are allowed

  Scenario: Execute safe query and display tabular results
    Given the database is initialized
    And the GOOGLE_API_KEY is configured
    And the model generates the SQL "SELECT * FROM students LIMIT 5"
    When I open the "Intelligent Query Assistance" page
    And I enter "Show first 5 students" in the query input
    And I click the "Get Answer" button
    Then I should see a "Generated SQL" section
    And I should see a results table with at least 1 row

  Scenario: Apply LIMIT when missing and inform the user
    Given the database is initialized
    And the GOOGLE_API_KEY is configured
    And the model generates the SQL "SELECT * FROM students"
    When I open the "Intelligent Query Assistance" page
    And I enter "Show all students" in the query input
    And I click the "Get Answer" button
    Then I should see an info message that a row limit was applied
    And I should see a results table

  Scenario: Show a helpful error when the generated SQL fails execution
    Given the database is initialized
    And the GOOGLE_API_KEY is configured
    And the model generates the SQL "SELECT * FROM does_not_exist"
    When I open the "Intelligent Query Assistance" page
    And I enter "Query a missing table" in the query input
    And I click the "Get Answer" button
    Then I should see an error that the query could not be executed
    And I should see guidance to use the schema to rephrase
