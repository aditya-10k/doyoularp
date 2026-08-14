# Web Collector

## Goal

Collect public evidence from portfolios, project websites and public pages.

## MVP Approach

Use normal HTTP requests first.

Preferred:
- httpx
- BeautifulSoup/lxml

Do not introduce browser automation unless the target genuinely requires JavaScript rendering.

## Extract

- page title
- headings
- visible text
- metadata
- links
- canonical URL
- basic status information

Remove:
- scripts
- styles
- obvious navigation boilerplate
- duplicate content

Preserve:
- project descriptions
- technologies
- feature descriptions
- metrics
- links
- relevant page headings

## Link Discovery

Discover:
- GitHub
- LinkedIn
- portfolio
- project
- app store
- play store
- documentation

## Safety

The web collector is a public-web reader.

Do not bypass:
- authentication
- CAPTCHA
- access controls

Do not attempt SSRF against:
- localhost
- private IP ranges
- cloud metadata endpoints
- internal hostnames

Validate and resolve URLs safely.

Use:
- connection timeouts
- response size limits
- redirect limits
- content-type checks

## Browser Automation

Not MVP.

If introduced later, isolate it behind a WebBrowserCollector interface.

Do not make Playwright/Selenium a requirement for every request.

## LinkedIn

Do not scrape LinkedIn in MVP.

If a LinkedIn page is publicly accessible through normal means, it may be treated as a webpage, but the product must not depend on it.

## Evidence

Every page becomes one or more evidence records with:

- source URL
- page title
- content
- extraction timestamp
- source type
