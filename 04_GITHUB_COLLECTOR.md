# GitHub Collector

## Goal

Collect public GitHub evidence for a candidate.

Input:

https://github.com/username

Output:
normalized GitHub profile/repository evidence.

## API Base

https://api.github.com

## Endpoints

GET /users/{username}

GET /users/{username}/repos

GET /repos/{owner}/{repo}

GET /repos/{owner}/{repo}/languages

GET /repos/{owner}/{repo}/commits

GET /repos/{owner}/{repo}/readme

GET /repos/{owner}/{repo}/contents

GET /repos/{owner}/{repo}/contributors

## Profile

Collect:

- username
- display name
- bio
- public repo count
- followers
- following
- created_at
- updated_at

## Repositories

Collect:

- name
- full_name
- URL
- description
- stars
- forks
- topics
- languages
- created_at
- updated_at
- pushed_at
- default branch
- license if available

## Commits

Collect:

- SHA
- author
- commit message
- committed date
- repository

Calculate candidate-authored commits where possible.

Do NOT assume all repository commits belong to the candidate.

## Contributors

Collect:
- username
- contribution count

This is critical when evaluating project ownership.

## README

Retrieve and decode README content.

## File Evidence

Prioritize:

README.md
package.json
requirements.txt
pyproject.toml
pubspec.yaml
go.mod
Cargo.toml
pom.xml
build.gradle
Dockerfile
docker-compose.yml
.github/
src/
app/

Do not blindly download every repository file.

## Technology Evidence

Technology can be inferred from:

- dependency manifests
- configuration
- source file extensions
- GitHub language statistics
- README

Use stronger evidence for dependency/configuration files than README claims.

## Pagination

Implement pagination correctly.

Do not only fetch the first 30 repositories and call it "all repos".

Use sensible limits to avoid excessive API usage.

## Rate Limits

Use authenticated GitHub requests.

Use:
- caching
- retries
- exponential backoff
- conditional requests where useful
- bounded concurrency

Never hammer GitHub.

## Ownership

A repository existing under a user's profile does not prove they personally built every part.

Compare:
- commit authorship
- contributor counts
- activity
- repository age
- relevant files

## Output Example

{
  "profile": {...},
  "repositories": [
    {
      "name": "travel-app",
      "languages": ["Dart"],
      "candidate_commit_count": 198,
      "total_commit_count": 240,
      "contributors": [...],
      "readme": "...",
      "files": [...]
    }
  ]
}
