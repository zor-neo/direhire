"use client";

import { useState } from "react";
import {
  EmployerPriorityCluster,
  JobAnalysisViewModel,
  RequirementView,
} from "../lib/job-analysis-view-model";

interface JobAnalysisViewProps {
  viewModel: JobAnalysisViewModel;
  titleOverride?: string;
  companyOverride?: string;
  locationOverride?: string;
  salaryOverride?: string;
  canonicalUrlOverride?: string;
}

export function JobAnalysisView({
  viewModel,
  titleOverride,
  companyOverride,
  locationOverride,
  salaryOverride,
  canonicalUrlOverride,
}: JobAnalysisViewProps) {
  const [showEvidence, setShowEvidence] = useState(false);

  const facts = {
    title: titleOverride || viewModel.facts.title,
    company: companyOverride || viewModel.facts.company,
    location: locationOverride || viewModel.facts.location,
    salary: salaryOverride || viewModel.facts.salary,
    canonicalUrl: canonicalUrlOverride || viewModel.facts.canonicalUrl,
  };

  const { roleReality, seniority, priorities, requirements, constraints, scenarios } = viewModel;

  return (
    <div className="job-analysis-view surface">
      {/* 1. Job Facts Header */}
      <header className="analysis-header">
        <div className="header-main">
          <span className="badge archetype-badge">{roleReality.primaryArchetype}</span>
          <h1 className="job-title">{facts.title}</h1>
          <p className="company-name">{facts.company}</p>
        </div>

        <div className="facts-bar">
          <span className="fact-pill location-pill">📍 {facts.location}</span>
          {facts.salary && facts.salary !== "Disclosed in listing" && (
            <span className="fact-pill salary-pill">💰 {facts.salary}</span>
          )}
          <span className="fact-pill remote-pill">⚡ {viewModel.remoteEligibility}</span>
          {facts.canonicalUrl && (
            <a
              href={facts.canonicalUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="canonical-link-button"
            >
              Original Listing ↗
            </a>
          )}
        </div>
      </header>

      {/* 2. Role Reality */}
      <section className="analysis-section role-reality-section">
        <h2 className="section-title">Role Reality</h2>
        <div className="reality-card">
          <p className="headline">{roleReality.headline}</p>
          <div className="reality-details">
            <div className="detail-item">
              <span className="label">Title Alignment:</span>
              <span className={`alignment-tag ${roleReality.titleAlignment.toLowerCase()}`}>
                {roleReality.titleAlignment}
              </span>
            </div>
            <div className="detail-item">
              <span className="label">Seniority:</span>
              <span className="seniority-tag">
                {seniority.assessment}
                {seniority.explicitMinYears != null && ` (${seniority.explicitMinYears}-${seniority.explicitMaxYears ?? ""} yrs)`}
              </span>
            </div>
            <div className="detail-item">
              <span className="label">Breadth:</span>
              <span className="breadth-tag">{roleReality.breadth}</span>
            </div>
          </div>
          <div className="mission-box">
            <h4>Primary Operational Mission</h4>
            <p>{roleReality.primaryMission}</p>
          </div>
          {seniority.reason && <p className="seniority-reason">💡 {seniority.reason}</p>}
        </div>
      </section>

      {/* 3. Employer Priorities */}
      <section className="analysis-section priorities-section">
        <h2 className="section-title">Employer Priorities</h2>

        <div className="compact-priorities-list">
          {priorities.core.length > 0 && (
            <div className="priority-group">
              <h3 className="group-label core-label">CORE</h3>
              <ul className="cluster-list">
                {priorities.core.map((cluster, idx) => (
                  <PriorityClusterItem key={idx} cluster={cluster} />
                ))}
              </ul>
            </div>
          )}

          {priorities.important.length > 0 && (
            <div className="priority-group">
              <h3 className="group-label important-label">IMPORTANT</h3>
              <ul className="cluster-list">
                {priorities.important.map((cluster, idx) => (
                  <PriorityClusterItem key={idx} cluster={cluster} />
                ))}
              </ul>
            </div>
          )}

          {priorities.supporting.length > 0 && (
            <div className="priority-group">
              <h3 className="group-label supporting-label">SUPPORTING</h3>
              <ul className="cluster-list">
                {priorities.supporting.map((cluster, idx) => (
                  <PriorityClusterItem key={idx} cluster={cluster} />
                ))}
              </ul>
            </div>
          )}

          {priorities.preferred.length > 0 && (
            <div className="priority-group">
              <h3 className="group-label preferred-label">PREFERRED</h3>
              <ul className="cluster-list">
                {priorities.preferred.map((cluster, idx) => (
                  <PriorityClusterItem key={idx} cluster={cluster} />
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

      {/* 4. Key Requirements */}
      {requirements.length > 0 && (
        <section className="analysis-section requirements-section">
          <h2 className="section-title">Key Requirements</h2>
          <div className="requirements-list">
            {requirements.map((req, idx) => (
              <RequirementItem key={idx} req={req} />
            ))}
          </div>
        </section>
      )}

      {/* 5. Job Constraints */}
      {constraints.length > 0 && (
        <section className="analysis-section constraints-section">
          <h2 className="section-title">Job Constraints</h2>
          <div className="constraints-tags">
            {constraints.map((item, idx) => (
              <div key={idx} className="constraint-badge">
                <span className="type">{item.constraintType}:</span> {item.description}
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 6. Real-Work Scenarios */}
      {scenarios.length > 0 && (
        <section className="analysis-section scenarios-section">
          <h2 className="section-title">What You'll Actually Do</h2>
          <div className="scenarios-list">
            {scenarios.map((scenario, idx) => (
              <div key={idx} className="scenario-card">
                <span className="scenario-num">Scenario #{idx + 1}</span>
                <p>{scenario}</p>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 7. Collapsible Evidence & Provenance Drawer */}
      <section className="analysis-section evidence-drawer-section">
        <button
          onClick={() => setShowEvidence(!showEvidence)}
          className="evidence-toggle-button"
        >
          {showEvidence ? "▼ Hide Detailed Evidence & Provenance" : "► View Detailed Evidence & Provenance"}
        </button>

        {showEvidence && (
          <div className="evidence-drawer">
            <h4>Original Employer Evidence Quotes</h4>
            <p className="drawer-subtitle">
              Quotes preserved in original language (e.g. Thai) for factual truthfulness.
            </p>

            <div className="evidence-quotes-list">
              {priorities.core.concat(priorities.important, priorities.preferred).map((c, idx) => (
                <div key={idx} className="quote-item">
                  <span className="quote-category">{c.name}:</span>
                  <blockquote className="quote-text">"{c.evidence}"</blockquote>
                  <span className="strength-tag">{c.evidenceStrength}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function PriorityClusterItem({ cluster }: { cluster: EmployerPriorityCluster }) {
  return (
    <li className="cluster-item">
      <div className="cluster-header">
        <span className="cluster-name">{cluster.name}</span>
        <span className="strength-badge">{cluster.evidenceStrength}</span>
      </div>
      <p className="cluster-reason">{cluster.reason}</p>
    </li>
  );
}

function RequirementItem({ req }: { req: RequirementView }) {
  return (
    <div className="requirement-row">
      <span className={`category-tag ${req.category.toLowerCase()}`}>{req.category}</span>
      <span className="requirement-title">{req.title}</span>
    </div>
  );
}
