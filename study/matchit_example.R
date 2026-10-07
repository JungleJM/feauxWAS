install_if_missing <- function(pkgs) {
  missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) > 0) {
    install.packages(missing, repos = "https://cloud.r-project.org")
  }
}

install_if_missing(c("MatchIt", "arrow", "cobalt", "dplyr"))

library(MatchIt)
library(arrow)
library(cobalt)
library(dplyr)

# The two group files from build_group_parquet.py, and where to
# write. With no arguments: the tutorial's synthetic files. The study's runner
# (run_phewas.py match) passes the real ones:
#   Rscript matchit_example.R <hat_group.parquet> <control_group.parquet> <out folder>
args <- commandArgs(trailingOnly = TRUE)
if (length(args) == 0) {
  args <- c("tutorial/synthetic_cosmos/hat/hat_group.parquet",
            "tutorial/synthetic_cosmos/ctrl/control_group.parquet",
            "tutorial/work")
}
if (length(args) != 3) {
  stop("give three arguments: hat_group.parquet, control_group.parquet, out folder; or none for the tutorial")
}
hat <- read_parquet(args[1])
control <- read_parquet(args[2])
out_dir <- args[3]

cohort <- bind_rows(hat, control) |>
  filter(EligibleForMatching == 1) |>
  mutate(
    HaT_Flag = as.integer(HaT_Flag),
    Sex = factor(Sex),
    Race = factor(Race),
    Ethnicity = factor(Ethnicity),
    IndexQuarter = factor(IndexQuarter)
  )

match <- matchit(
  HaT_Flag ~ AgeAtIndex +
    YearsBeforeIndex +
    YearsAfterIndex +
    log1p(ClinicVisits365Before) +
    Race +
    Ethnicity,
  data = cohort,
  method = "nearest",
  distance = "glm",
  exact = ~ Sex + IndexQuarter,
  ratio = 10,
  replace = FALSE,
  caliper = 0.2,
  std.caliper = TRUE
)

print(summary(match, un = FALSE))

dir.create(out_dir, showWarnings = FALSE, recursive = TRUE)
matched <- match.data(match)
write_parquet(matched, file.path(out_dir, "matched_cohort.parquet"))

png(file.path(out_dir, "matchit_balance_love_plot.png"), width = 1200, height = 800)
print(love.plot(match, threshold = 0.1))
dev.off()
