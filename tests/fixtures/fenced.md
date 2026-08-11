# Fenced Code Fixture

Heading-like lines inside fenced blocks must never reach the table of
contents, and the three identical `## Real Heading` titles must produce
three distinct anchors.

<!-- toc -->
- [Fenced Code Fixture](#fenced-code-fixture)
  - [Real Heading](#real-heading)
  - [Real Heading](#real-heading-1)
  - [Real Heading](#real-heading-2)
  - [Ending](#ending)
<!-- /toc -->

## Real Heading

A backtick fence whose contents look like headings:

```sh
# Backtick Ghost One
## Backtick Ghost Two
###### Backtick Ghost Six
```

## Real Heading

A tilde fence whose contents look like headings:

~~~python
# Tilde Ghost One
### Tilde Ghost Three
~~~

## Real Heading

A backtick fence that contains tildes, and a tilde fence that contains
backticks; neither inner run closes the outer fence:

```text
~~~
# Nested Tilde Ghost
~~~
```

~~~text
```
# Nested Backtick Ghost
```
~~~

## Ending
