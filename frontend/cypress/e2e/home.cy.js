describe("Home page", () => {
  it("renders records from the API", () => {
    cy.visit("/");
    cy.contains("h1", "Full-Stack Starter Dashboard").should("be.visible");
    cy.get("[data-testid="records-list"]").should("exist");
    cy.request("/api/records").then((response) => {
      expect(response.body.data).to.include("Example record A");
    });
    cy.contains("li", "Example record A", { timeout: 30000 }).should("be.visible");
  });
});
