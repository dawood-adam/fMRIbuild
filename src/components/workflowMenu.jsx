import React, { useState } from 'react';
import WorkflowMenuItem from './workflowMenuItem';
import { toolsByLibrary, libraryOrder, dummyNodes } from '../data/toolData';
import '../styles/workflowMenu.css';

function WorkflowMenu() {
  const [expandedSections, setExpandedSections] = useState({
    DummyNodes: false,
    FSL: false,
    AFNI: false,
    SPM: false,
    FreeSurfer: false,
    ANTs: false
  });

  const toggleSection = (library) => {
    setExpandedSections(prev => ({
      ...prev,
      [library]: !prev[library]
    }));
  };

  const handleDragStart = (event, name, isDummy = false) => {
    event.dataTransfer.setData('node/name', name);
    event.dataTransfer.setData('node/isDummy', isDummy.toString());
  };

  // Count total tools in a library
  const getToolCount = (library) => {
    const libraryData = toolsByLibrary[library];
    if (!libraryData || Object.keys(libraryData).length === 0) return 0;
    return Object.values(libraryData).reduce((sum, tools) => sum + tools.length, 0);
  };

  return (
    <div className="workflow-menu-container">
      <div className="workflow-menu">
        {/* I/O (Dummy Nodes) Section */}
        <div className="library-section">
          <div
            className={`library-header ${expandedSections['DummyNodes'] ? 'expanded' : ''}`}
            onClick={() => toggleSection('DummyNodes')}
          >
            <span className="chevron">{expandedSections['DummyNodes'] ? '▼' : '▶'}</span>
            <span className="library-name">I/O</span>
            <span className="tool-count">2</span>
          </div>

          {expandedSections['DummyNodes'] && (
            <div className="library-tools">
              <div className="subsection-tools">
                {dummyNodes['I/O'].map((tool, index) => (
                  <WorkflowMenuItem
                    key={`dummy-${index}`}
                    name={tool.name}
                    toolInfo={{
                      fullName: tool.fullName,
                      function: tool.function,
                      typicalUse: tool.typicalUse
                    }}
                    onDragStart={(event, name) => handleDragStart(event, name, true)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Library Sections */}
        {libraryOrder.map((library) => {
          const libraryData = toolsByLibrary[library];
          const isExpanded = expandedSections[library];
          const toolCount = getToolCount(library);
          const subsections = Object.keys(libraryData || {});

          return (
            <div key={library} className="library-section">
              <div
                className={`library-header ${isExpanded ? 'expanded' : ''}`}
                onClick={() => toggleSection(library)}
              >
                <span className="chevron">{isExpanded ? '▼' : '▶'}</span>
                <span className="library-name">{library}</span>
                <span className="tool-count">
                  {toolCount > 0 ? `${toolCount}` : ''}
                </span>
              </div>

              {isExpanded && (
                <div className="library-tools">
                  {toolCount === 0 ? (
                    <div className="coming-soon">Coming Soon - requires MATLAB</div>
                  ) : (
                    subsections.map((subsection) => (
                      <div key={subsection} className="subsection">
                        <div className="subsection-header">{subsection}</div>
                        <div className="subsection-tools">
                          {libraryData[subsection].map((tool, index) => (
                            <WorkflowMenuItem
                              key={`${library}-${subsection}-${index}`}
                              name={tool.name}
                              toolInfo={{
                                fullName: tool.fullName,
                                function: tool.function,
                                typicalUse: tool.typicalUse,
                                docUrl: tool.docUrl
                              }}
                              onDragStart={handleDragStart}
                            />
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default WorkflowMenu;
