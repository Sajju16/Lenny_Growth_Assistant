export const mockConversations = [
  {
    id: 'first-100-customers',
    title: 'Finding Our First 100 Customers',
    category: 'Growth Strategy',
    group: 'Today',
    artifactId: 'artifact-first-100',
    messages: [
      {
        id: 'm1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: '10:24 AM',
        content: 'How can an early-stage startup acquire its first 100 customers?'
      },
      {
        id: 'm2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: '10:24 AM',
        contentIntro: "Acquiring your first 100 customers is fundamentally an **unscalable, high-conviction manual effort**. Across 120+ founder interviews on Lenny's Podcast, three distinct non-scalable playbooks emerge repeatedly:",
        sections: [
          {
            num: '01.',
            title: 'Hand-to-Hand Combat & Direct Outreach',
            body: 'Founders personally knock on doors, send hyper-personalized cold LinkedIn memos, or physically sit next to prospects. The objective is not scalable lead volume—it is zero-latency qualification and direct feedback loops.',
            citations: [
              { type: 'mic', label: 'Ep #84: Peter Kazanjy (Founding Sales)' },
              { type: 'doc', label: 'Substack Genesis Playbook #142' }
            ]
          },
          {
            num: '02.',
            title: 'Infiltrating Existing High-Gravity Communities',
            body: 'Identify existing subreddits, Slack channels, WhatsApp circles, or Discord servers where your Ideal Customer Profile already laments their acute problem. Become an authoritative contributor before ever pitching software.',
            citations: [
              { type: 'mic', label: 'Ep #112: Gina Bianchini (Mighty Networks)' }
            ]
          },
          {
            num: '03.',
            title: 'The "Trojan Horse" Free Audit / Teardown',
            body: 'Offer complimentary deep audits, automated teardowns, or custom benchmark reports. When you deliver undeniable diagnostic value upfront for free, transitioning 15–20% of respondents into pilot customers becomes frictionless.',
            citations: []
          }
        ],
        canvasCard: {
          tag: 'Synthesized Playbook Canvas',
          title: 'First 100 Customers — Growth Playbook (v1.0)',
          artifactId: 'artifact-first-100'
        },
        footerInfo: 'Indexed 6 founder transcripts'
      }
    ]
  },
  {
    id: 'b2b-plg-loops',
    title: 'B2B PLG Acquisition Loops',
    category: 'Product-Led Growth',
    group: 'Today',
    artifactId: 'artifact-b2b-plg',
    messages: [
      {
        id: 'm-plg-1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: '9:15 AM',
        content: 'How should we design organic product loops so our free users invite their peers without feeling spammy?'
      },
      {
        id: 'm-plg-2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: '9:16 AM',
        contentIntro: 'Product-led growth loops succeed when the **invitation or share is an essential utility for the inviter**, not an artificial referral bonus. From conversations with Elena Verna, Casey Winters, and Guillaume Cabane:',
        sections: [
          {
            num: '01.',
            title: 'Collaborative Work Inherent Loops',
            body: 'Design single-player utility that quickly hits a multiplayer boundary. Once an analysis or canvas is built, requesting review from a stakeholder triggers natural viral onboarding.',
            citations: [
              { type: 'mic', label: 'Ep #63: Elena Verna (B2B PLG Strategy)' }
            ]
          },
          {
            num: '02.',
            title: 'Programmatic Public Artifacts',
            body: 'Let users publish or embed output on their company wikis and public channels with high-utility previews and subtle attribution.',
            citations: [
              { type: 'mic', label: 'Ep #39: Casey Winters (Growth Loops)' }
            ]
          }
        ],
        canvasCard: {
          tag: 'Synthesized Playbook Canvas',
          title: 'B2B PLG Acquisition Loops — Blueprint (v2.0)',
          artifactId: 'artifact-b2b-plg'
        },
        footerInfo: 'Indexed 8 founder transcripts'
      }
    ]
  },
  {
    id: 'pmf-survey',
    title: 'Superhuman PMF Engine Score',
    category: 'Product Strategy',
    group: 'Today',
    artifactId: 'artifact-pmf-survey',
    messages: [
      {
        id: 'm-pmf-1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: 'Yesterday',
        content: 'What is the exact methodology Rahul Vohra used to quantify product-market fit at Superhuman?'
      },
      {
        id: 'm-pmf-2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: 'Yesterday',
        contentIntro: 'Rahul Vohra adapted Sean Ellis\'s classic 40% rule into an **iterative 4-step Product-Market Fit Engine**. The core benchmark is asking users: *"How would you feel if you could no longer use the product?"*',
        sections: [
          {
            num: '01.',
            title: 'Segmenting by High-Expectation Customers (HXC)',
            body: 'Focus exclusively on respondents who answered "Very Disappointed". Analyze what specific features and capabilities they value above all else.',
            citations: [
              { type: 'mic', label: 'Ep #28: Rahul Vohra (The PMF Engine)' }
            ]
          },
          {
            num: '02.',
            title: 'The 50/50 Roadmap Rule',
            body: 'Allocate 50% of engineering bandwidth to doubling down on what your "Very Disappointed" users love, and 50% to resolving the blockades of "Somewhat Disappointed" users.',
            citations: []
          }
        ],
        canvasCard: {
          tag: 'Framework Canvas',
          title: 'Superhuman PMF Engine Scorecard',
          artifactId: 'artifact-pmf-survey'
        },
        footerInfo: 'Indexed 4 founder transcripts'
      }
    ]
  },
  {
    id: 'pricing-tier',
    title: 'Expansion Pricing Grid',
    category: 'Monetization',
    group: 'Previous 7 Days',
    artifactId: null,
    messages: [
      {
        id: 'm-pr-1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: 'Oct 3',
        content: 'When is seat-based pricing inferior to usage-based pricing in modern B2B SaaS?'
      },
      {
        id: 'm-pr-2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: 'Oct 3',
        contentIntro: 'Seat-based pricing creates **internal friction against user expansion**, directly contradicting PLG principles. The consensus across Patrick Campbell and Kyle Poyar interviews highlights hybrid models:',
        sections: [
          {
            num: '01.',
            title: 'Aligning with the Value Metric',
            body: 'Your price must scale with the metric that grows alongside the customer\'s perceived business ROI (e.g. active contacts, API credits, compute tokens).',
            citations: [
              { type: 'mic', label: 'Ep #95: Patrick Campbell (Pricing Secrets)' }
            ]
          }
        ],
        canvasCard: null,
        footerInfo: 'Indexed 5 pricing teardowns'
      }
    ]
  },
  {
    id: 'retention-cohorts',
    title: 'Cohort Retention Breakdown',
    category: 'Analytics',
    group: 'Previous 7 Days',
    artifactId: null,
    messages: [
      {
        id: 'm-ret-1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: 'Oct 2',
        content: 'How can we diagnose whether cohort curve flattening is healthy or a false plateau?'
      },
      {
        id: 'm-ret-2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: 'Oct 2',
        contentIntro: 'Look for the **terminal curve angle after day 30 and day 90**. If the curve parallels the x-axis, you have retained a durable core of high-frequency power users.',
        sections: [
          {
            num: '01.',
            title: 'The Smiling Retention Curve',
            body: 'In mature PLG products, unengaged churned users reactivate through organizational adoption, creating net-negative revenue churn.',
            citations: [
              { type: 'mic', label: 'Ep #51: Dan Hockenmaier (Retention Dynamics)' }
            ]
          }
        ],
        canvasCard: null,
        footerInfo: 'Indexed 3 analytics deep-dives'
      }
    ]
  },
  {
    id: 'onboarding-dropoff',
    title: 'Self-Serve Funnel Diagnosis',
    category: 'Activation',
    group: 'Previous 7 Days',
    artifactId: null,
    messages: [
      {
        id: 'm-onb-1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: 'Sep 29',
        content: 'Where do most self-serve users abandon the activation flow before the "Aha" moment?'
      },
      {
        id: 'm-onb-2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: 'Sep 29',
        contentIntro: 'The #1 friction point is **premature authentication or setup homework** before showing tangible product value. The quickest fix is concierge onboarding or immediate template sandboxes.',
        sections: [
          {
            num: '01.',
            title: 'Time-to-Value (TTV) Compression',
            body: 'Strip every configuration input that is not strictly necessary for the first session experience.',
            citations: [
              { type: 'mic', label: 'Ep #78: Darius Contractor (Speed of Onboarding)' }
            ]
          }
        ],
        canvasCard: null,
        footerInfo: 'Indexed 6 teardowns'
      }
    ]
  },
  {
    id: 'growth-model',
    title: 'Bottom-Up GTM Formula',
    category: 'GTM Strategy',
    group: '30 Days Ago',
    artifactId: null,
    messages: [
      {
        id: 'm-gtm-1',
        sender: 'user',
        authorName: 'Alex Kim',
        authorRole: 'Head of Growth',
        timestamp: 'Sep 12',
        content: 'What is the bridge from bottom-up self-serve to top-down sales-assist?'
      },
      {
        id: 'm-gtm-2',
        sender: 'assistant',
        authorName: 'Lenny Assistant',
        timestamp: 'Sep 12',
        contentIntro: 'Product-Led Sales (PLS) triggers when a cluster of free workspaces reaches a Product Qualified Account (PQA) threshold. Sales should enter as customer success consultants rather than cold closers.',
        sections: [
          {
            num: '01.',
            title: 'PQA Scoring Mechanics',
            body: 'Set triggers on team usage frequency, enterprise feature clicks, and domain clustering.',
            citations: [
              { type: 'mic', label: 'Ep #104: Pete Prowitt (Product Qualified Leads)' }
            ]
          }
        ],
        canvasCard: null,
        footerInfo: 'Indexed 7 transcripts'
      }
    ]
  }
];
