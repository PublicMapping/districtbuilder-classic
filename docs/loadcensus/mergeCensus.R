###  Helper R Script for Census Data loading
###  This merges the PL data into the shapefile block data and
###  Generates quantiles for the choropleths.
###     
###  NOTE: Since this is run in rpy, the results are visible to python
###  Limit use of values to q_*, sum_TOTPOP, and has_election_data -- others may change


# merge census and supplementary data
library(foreign) 
setwd('/projects/PublicMapping/data')
supp.df <-read.csv("redist_data.csv",stringsAsFactors=F,colClasses=c(GEOID10="character"))
census.df<-read.dbf("census_blocks.dbf",as.is=TRUE)
census.df$orig_rows<-1:dim(census.df)[1]
merged.df<-merge(census.df,supp.df,by="GEOID10")
merged.df <- merged.df[order(merged.df$orig_rows),]
merged.df$orig_rows<-NULL

if (!all(census.df$GEOID10==merged.df$GEOID10)|| sum(merged.df$TOTPOP)==0) { 
       stop('Census merge mismatch')
}

# check for the existence of election variables in the data, choose the # best one
electionvar <- names(merged.df)[charmatch (c("VOTE_DEM","GOV10_DEM","GOV09_DEM","GOV08_DEM",
"PRS10_DEM","PRS09_DEM","PRS08_DEM"),names(merged.df))]
electionvar<-electionvar[which(!is.na(electionvar))][1]
if (is.na(electionvar)) {        
	has_election_data<-0
} else {
	has_election_data<-1  
	merged.df$VOTE_DEM<-merged.df[electionvar]
        merged.df$VOTE_REP<-merged.df[sub("_DEM","_REP",electionvar)]        
	merged.df$VOTE_TOT<-merged.df$VOTE_DEM+merged.df$VOTE_REP
}

# write merged file
options(warn=-1)
write.dbf(merged.df,"census_blocks.dbf")
options(warn=0)

# write template files
write.table(cbind(as.character(merged.df$GEOID10),merged.df$CD),file="congress_generated_index.csv",quote=F,row.names=F,col.names=F,sep=",")
write.table(cbind(as.character(merged.df$GEOID10),merged.df$SLDL),file="house_generated_index.csv",quote=F,row.names=F,col.names=F,sep=",")
write.table(cbind(as.character(merged.df$GEOID10),merged.df$SLDU),file="senate_generated_index.csv",quote=F,row.names=F,col.names=F,sep=",")

