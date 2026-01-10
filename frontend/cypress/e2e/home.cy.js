describe("Home page", () => {
  it("renders records from the API", () => {
    cy.visit("/");
    cy.contains("h1", "Full-Stack Starter Dashboard").should("be.visible");
    cy.get('[data-testid="records-list"]').should("exist");
    cy.contains("li", "Example record A", { timeout: 30000 }).should("be.visible");
  });
});


